from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .assumptions import SPECIAL_PROFILES, build_scenarios, infer_company_type, resolve_forward_estimates
from .capex import split_capex
from .confidence import BASE_WEIGHTS, aggregate_targets, confidence_score, normalize_model_weights, rating_from_targets
from .dcf import dcf_sensitivity_table, run_three_stage_dcf
from .models import Facts, ModelOutput, build_facts, safe_div
from .multiples import derive_reasonable_multiples
from .quality import build_data_quality, calculate_quality_score
from .reverse import reverse_dcf, reverse_multiples


def _load_consensus_from_db(ticker: str) -> dict[str, Any] | None:
    try:
        from ..db import connect, row_to_dict

        with connect() as conn:
            row = conn.execute("SELECT * FROM consensus_estimates WHERE ticker = ?", (ticker.upper(),)).fetchone()
        return row_to_dict(row)
    except Exception:
        return None


def _load_history_from_db(ticker: str) -> list[dict[str, Any]]:
    try:
        from ..db import connect

        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM valuation_multiples_history WHERE ticker = ? ORDER BY date DESC LIMIT 80",
                (ticker.upper(),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _load_peer_snapshot_from_db(ticker: str) -> list[dict[str, Any]]:
    try:
        from ..db import connect

        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM peer_valuation_snapshot WHERE ticker = ? ORDER BY date DESC LIMIT 50",
                (ticker.upper(),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _scenario_probability(request: Any | None, key: str, fallback: float) -> float:
    scenario = getattr(request, key, None)
    if scenario is not None and getattr(scenario, "probability", None) is not None:
        return float(scenario.probability)
    return fallback


def _price_from_ev(value: float, facts: Facts) -> float:
    return safe_div(value + facts.net_cash, facts.diluted_shares)


def _weight_reason(model: str, company_type: str, source: str = "") -> str:
    reasons = {
        "three_stage_dcf": "DCF 是该公司类型的内在价值锚，且 CAPEX 已拆分维护性与成长性。",
        "forward_pe": "盈利已经可用时，Forward P/E 更接近市场给 12M 目标价的方式。",
        "ev_ebitda": "EV/EBITDA 可校验经营利润与资本结构，适合盈利型科技和平台公司。",
        "ev_sales": "收入倍数适合利润尚未完全释放的软件或高成长公司，但会受 Rule of 40 约束。",
        "rule_of_40_ev_sales": "软件公司需要把收入增长和 FCF margin 放在一起看，Rule of 40 用来调节收入倍数。",
        "peg": "PEG 用 EPS 增速约束高 PE 是否合理。",
        "fcf_yield": "FCF Yield 把公司当成现金流资产，利率越高要求收益率越高。",
        "reverse_check": "反向估值不直接预测目标价，而是惩罚需要过度乐观假设的价格。",
        "mid_cycle_earnings": "周期股使用中周期利润，避免用峰值利润乘高倍数。",
    }
    suffix = f" 倍数来源：{source}。" if source else ""
    return reasons.get(model, f"{company_type} 的辅助校验模型。") + suffix


def _build_model_outputs(
    facts: Facts,
    company_type: str,
    scenarios: dict[str, dict[str, float]],
    dcf_outputs: dict[str, dict[str, Any]],
    forward: dict[str, Any],
    multiples: dict[str, Any],
    reverse: dict[str, Any],
) -> list[ModelOutput]:
    weights = BASE_WEIGHTS.get(company_type, BASE_WEIGHTS["default"])
    eps = (forward["eps_next_year"]["value"] or 0)
    eps_growth = (forward["long_term_eps_growth"]["value"] or 0)
    revenue = (forward["revenue_next_year"]["value"] or 0)
    ebitda = (forward["ebitda_next_year"]["value"] or 0)
    fcf = (forward["fcf_next_year"]["value"] or 0)
    pe = multiples["pe"]
    ev_sales = multiples["ev_sales"]
    ev_ebitda = multiples["ev_ebitda"]
    fcf_yields = (
        max(facts.ten_year_yield + 0.055, 0.080),
        max(facts.ten_year_yield + 0.035, 0.060),
        max(facts.ten_year_yield + 0.020, 0.048),
    )
    peg_pe = tuple(max(8.0, eps_growth * 100 * peg) for peg in (1.0, 1.4, 1.8))
    reverse_adjust = 0.88 if reverse["difficulty"] == "very_aggressive" else 0.94 if reverse["difficulty"] == "aggressive" else 1.0

    models = [
        ModelOutput(
            "three_stage_dcf",
            "三阶段 FCFF DCF",
            dcf_outputs["bear"]["per_share"],
            dcf_outputs["base"]["per_share"],
            dcf_outputs["bull"]["per_share"],
            weights.get("three_stage_dcf", 0),
            {"scenarios": scenarios, "capex_split": dcf_outputs["base"].get("capex_split")},
            {"financials": "reported", "capex_split": dcf_outputs["base"].get("capex_split", {}).get("method", "system")},
            _weight_reason("three_stage_dcf", company_type),
            dcf_outputs["base"].get("fallback_notes", []),
        ),
        ModelOutput(
            "forward_pe",
            "Forward P/E",
            eps * pe[0],
            eps * pe[1],
            eps * pe[2],
            weights.get("forward_pe", 0),
            {"forward_eps": eps, "pe_multiples": pe},
            {"forward_eps": forward["eps_next_year"]["source"], "multiples": multiples["sources"]["pe"]},
            _weight_reason("forward_pe", company_type, multiples["sources"]["pe"]),
        ),
        ModelOutput(
            "peg",
            "PEG 成长调整",
            eps * peg_pe[0],
            eps * peg_pe[1],
            eps * peg_pe[2],
            weights.get("peg", 0),
            {"forward_eps": eps, "long_term_eps_growth": eps_growth, "peg_pe": peg_pe},
            {"forward_eps": forward["eps_next_year"]["source"], "eps_growth": forward["long_term_eps_growth"]["source"]},
            _weight_reason("peg", company_type),
        ),
        ModelOutput(
            "ev_ebitda",
            "EV/EBITDA",
            _price_from_ev(ebitda * ev_ebitda[0], facts),
            _price_from_ev(ebitda * ev_ebitda[1], facts),
            _price_from_ev(ebitda * ev_ebitda[2], facts),
            weights.get("ev_ebitda", 0),
            {"forward_ebitda": ebitda, "ev_ebitda_multiples": ev_ebitda},
            {"forward_ebitda": forward["ebitda_next_year"]["source"], "multiples": multiples["sources"]["ev_ebitda"]},
            _weight_reason("ev_ebitda", company_type, multiples["sources"]["ev_ebitda"]),
        ),
        ModelOutput(
            "ev_sales",
            "EV/Revenue",
            _price_from_ev(revenue * ev_sales[0], facts),
            _price_from_ev(revenue * ev_sales[1], facts),
            _price_from_ev(revenue * ev_sales[2], facts),
            weights.get("ev_sales", 0),
            {"forward_revenue": revenue, "ev_sales_multiples": ev_sales},
            {"forward_revenue": forward["revenue_next_year"]["source"], "multiples": multiples["sources"]["ev_sales"]},
            _weight_reason("ev_sales", company_type, multiples["sources"]["ev_sales"]),
            [multiples["rule_of_40"]["warning"]] if multiples["rule_of_40"].get("warning") else [],
        ),
        ModelOutput(
            "rule_of_40_ev_sales",
            "Rule of 40 EV/Revenue",
            _price_from_ev(revenue * ev_sales[0] * 0.92, facts),
            _price_from_ev(revenue * ev_sales[1], facts),
            _price_from_ev(revenue * ev_sales[2] * 1.08, facts),
            weights.get("rule_of_40_ev_sales", 0),
            {"forward_revenue": revenue, "rule_of_40": multiples["rule_of_40"], "ev_sales_multiples": ev_sales},
            {"forward_revenue": forward["revenue_next_year"]["source"], "multiples": multiples["sources"]["ev_sales"]},
            _weight_reason("rule_of_40_ev_sales", company_type, multiples["sources"]["ev_sales"]),
            [multiples["rule_of_40"]["warning"]] if multiples["rule_of_40"].get("warning") else [],
        ),
        ModelOutput(
            "fcf_yield",
            "FCF Yield",
            safe_div(safe_div(fcf, facts.diluted_shares), fcf_yields[0]),
            safe_div(safe_div(fcf, facts.diluted_shares), fcf_yields[1]),
            safe_div(safe_div(fcf, facts.diluted_shares), fcf_yields[2]),
            weights.get("fcf_yield", 0),
            {"forward_fcf": fcf, "target_fcf_yields": fcf_yields},
            {"forward_fcf": forward["fcf_next_year"]["source"], "ten_year_yield": "local_setting_or_fred"},
            _weight_reason("fcf_yield", company_type),
        ),
    ]
    if company_type == "cyclical":
        operating_values = [float(row.get("operating_income") or 0) for row in facts.annual_history if row.get("operating_income")]
        mid_cycle = sum(operating_values[-10:]) / len(operating_values[-10:]) if operating_values else facts.operating_income
        models.append(
            ModelOutput(
                "mid_cycle_earnings",
                "Mid-cycle Earnings",
                safe_div(mid_cycle * 0.82 * pe[0], facts.diluted_shares),
                safe_div(mid_cycle * 0.82 * pe[1], facts.diluted_shares),
                safe_div(mid_cycle * 0.82 * pe[2], facts.diluted_shares),
                weights.get("mid_cycle_earnings", 0),
                {"mid_cycle_operating_income": mid_cycle, "pe_multiples": pe},
                {"history": "reported", "multiples": multiples["sources"]["pe"]},
                _weight_reason("mid_cycle_earnings", company_type),
                ["周期股估值使用中周期利润，避免峰值利润外推。"],
            )
        )
    models.append(
        ModelOutput(
            "reverse_check",
            "Reverse Expectations Check",
            dcf_outputs["base"]["per_share"] * reverse_adjust * 0.90,
            dcf_outputs["base"]["per_share"] * reverse_adjust,
            dcf_outputs["base"]["per_share"] * min(1.08, reverse_adjust + 0.08),
            weights.get("reverse_check", 0),
            {"difficulty": reverse["difficulty"], "implied_revenue_cagr_5y": reverse["implied_revenue_cagr_5y"]},
            {"current_price": "market_price", "reverse_dcf": "system_calculated"},
            _weight_reason("reverse_check", company_type),
        )
    )
    return normalize_model_weights(models)


def _target_prices(aggregate: dict[str, float], current_price: float) -> dict[str, float]:
    base = aggregate["base"]
    bear = min(aggregate["bear"], base)
    bull = max(aggregate["bull"], base)
    return {
        "bear": bear,
        "base": base,
        "bull": bull,
        "range_low": min(bear, base * 0.90),
        "range_high": max(bull, base * 1.10),
        "upside_base": safe_div(base - current_price, current_price),
        "upside_bull": safe_div(bull - current_price, current_price),
        "downside_bear": safe_div(bear - current_price, current_price),
    }


def run_target_price_calculator(facts_dict: dict[str, Any], request: Any | None = None) -> dict[str, Any]:
    facts = build_facts(facts_dict)
    manual_overrides = dict(getattr(request, "manual_overrides", {}) or {})
    consensus = getattr(request, "consensus", None)
    db_consensus = _load_consensus_from_db(facts.ticker) if consensus is None else None
    history = manual_overrides.get("multiples_history") or _load_history_from_db(facts.ticker)
    peer_snapshot = manual_overrides.get("peer_snapshot") or _load_peer_snapshot_from_db(facts.ticker)

    company_type = infer_company_type(facts, facts.company_profile, facts.annual_history)
    company_state = SPECIAL_PROFILES.get(facts.ticker, {}).get("company_state", company_type)
    scenarios = build_scenarios(company_type, request, manual_overrides)
    forward_estimates = resolve_forward_estimates(facts, consensus, facts.annual_history, db_consensus)
    forward = forward_estimates.to_dict()
    capex_split = split_capex(facts, facts.annual_history, company_type, manual_overrides if getattr(request, "use_capex_split", True) else {"maintenance_capex_ratio": 1})

    dcf_outputs: dict[str, dict[str, Any]] = {}
    for key, scenario in scenarios.items():
        dcf_outputs[key] = run_three_stage_dcf(facts, scenario, capex_split)
        dcf_outputs[key]["capex_split"] = capex_split
    dcf_sensitivity = dcf_sensitivity_table(facts, scenarios["base"], capex_split)
    multiples = derive_reasonable_multiples(company_type, facts, forward, peer_snapshot, history)
    reverse_dcf_output = reverse_dcf(facts, scenarios["base"], capex_split) if getattr(request, "use_reverse_dcf", True) else {}
    reverse_multiples_output = reverse_multiples(facts, forward, multiples, peer_snapshot)
    reverse_expectations = {**reverse_dcf_output, "multiples": reverse_multiples_output}

    warnings = list(capex_split.get("warnings", []))
    for item in forward.values():
        if item.get("source") == "system_estimate":
            warnings.append("forward consensus 缺失，系统使用历史增长和利润率估算，非市场共识。")
            break
    data_quality = build_data_quality(forward, warnings, facts)
    models = _build_model_outputs(facts, company_type, scenarios, dcf_outputs, forward, multiples, reverse_dcf_output)
    aggregate = aggregate_targets(models)
    target_price = _target_prices(aggregate, facts.price)
    confidence = confidence_score(facts, models, data_quality, dcf_outputs["base"])
    rating = rating_from_targets(target_price["upside_base"], confidence, reverse_dcf_output.get("difficulty", "reasonable"))
    quality_score, quality_breakdown = calculate_quality_score(facts)
    model_dicts = [model.to_dict() for model in models]

    result = {
        "ticker": facts.ticker,
        "fiscal_year": facts.fiscal_year,
        "methodology_version": "V3.0/V4.0 target price calculator",
        "current_price": facts.price,
        "market_cap": facts.market_cap,
        "enterprise_value": facts.enterprise_value,
        "net_cash": facts.net_cash,
        "company_type": company_type,
        "company_state": company_state,
        "horizon": getattr(request, "horizon", "12m"),
        "target_price": target_price,
        "intrinsic_value_3y": {
            "range_low": dcf_outputs["bear"]["per_share"],
            "base": dcf_outputs["base"]["per_share"],
            "range_high": dcf_outputs["bull"]["per_share"],
        },
        "rating": rating,
        "confidence": confidence,
        "quality_score": quality_score,
        "quality_breakdown": quality_breakdown,
        "forward_estimates": forward,
        "scenarios": scenarios,
        "capex_split": capex_split,
        "dcf": {
            "bear": dcf_outputs["bear"],
            "base": dcf_outputs["base"],
            "bull": dcf_outputs["bull"],
            "sensitivity": dcf_sensitivity,
        },
        "multiples": multiples,
        "model_outputs": model_dicts,
        "reverse_expectations": reverse_expectations,
        "data_quality": data_quality,
        "key_risks": _key_risks(company_type, reverse_dcf_output, data_quality, capex_split),
        "plain_language": _plain_language(facts, target_price, rating, reverse_expectations, company_type, data_quality),
        "disclaimer": "本工具用于估值假设检查和目标价计算，不构成投资建议。",
    }
    result.update(_legacy_view(result, facts, quality_breakdown))
    return result


def _key_risks(company_type: str, reverse_dcf_output: dict[str, Any], data_quality: dict[str, Any], capex_split: dict[str, Any]) -> list[str]:
    risks = []
    if reverse_dcf_output.get("difficulty") in {"aggressive", "very_aggressive"}:
        risks.append("当前价格隐含较高增长或利润率兑现要求。")
    if company_type in {"high_growth_software", "high_growth_profitable_tech"}:
        risks.append("高成长估值对收入增速放缓和倍数收缩高度敏感。")
    if capex_split.get("growth_capex", 0) > capex_split.get("maintenance_capex", 0):
        risks.append("成长 CAPEX 需要在未来转化为更高收入或现金流，否则 DCF 会下修。")
    if data_quality.get("system_estimates"):
        risks.append("forward 共识数据缺失，部分目标价依赖系统估算。")
    return risks


def _plain_language(facts: Facts, target: dict[str, float], rating: str, reverse_expectations: dict[str, Any], company_type: str, data_quality: dict[str, Any]) -> dict[str, str]:
    return {
        "one_sentence": f"{facts.ticker} 的 Base Target 约 ${target['base']:.2f}，相对当前价 upside/downside 为 {target['upside_base'] * 100:.1f}%，评级为 {rating}。",
        "what_market_is_pricing": reverse_expectations.get("plain_language", ""),
        "what_must_go_right": "收入增速、利润率和资本开支回报需要接近或超过 base 情景，倍数不能显著低于动态合理区间。",
        "what_can_go_wrong": "如果 forward 数据只是系统估算、成长 CAPEX 回报不足，或市场倍数回落，目标价区间会明显下移。",
        "data_quality": f"数据质量为 {data_quality['level']}，系统估算字段：{', '.join(data_quality['system_estimates']) or '无'}。",
        "headline": f"{facts.ticker} 目标价计算器：{rating}。",
        "expectation": reverse_expectations.get("plain_language", ""),
        "v3_conclusion": f"Bear/Base/Bull 目标价约为 ${target['bear']:.0f} / ${target['base']:.0f} / ${target['bull']:.0f}。",
    }


def _legacy_view(result: dict[str, Any], facts: Facts, quality_breakdown: dict[str, Any]) -> dict[str, Any]:
    target = result["target_price"]
    capex_split = result["capex_split"]
    actual_fcf = facts.actual_fcf
    owner_earnings = facts.ocf - capex_split["maintenance_capex"] - facts.sbc * 0.5
    fcf_yield = safe_div(actual_fcf, facts.market_cap)
    ocf_yield = safe_div(facts.ocf, facts.market_cap)
    judgement_map = {
        "buy": "有吸引力",
        "accumulate": "偏便宜",
        "hold": "合理",
        "trim": "偏贵",
        "sell_or_avoid": "高风险高估",
        "too_uncertain": "数据不足",
    }
    level_map = {"high": "高", "medium_high": "中高", "medium": "中", "low": "低"}
    model_consistency = {
        "level": level_map.get(result["confidence"]["level"], result["confidence"]["level"]),
        "score": result["confidence"]["score"],
        "price_position": "低于目标中枢" if facts.price < target["base"] else "高于目标中枢",
        "plain_language": "V4.0 会按公司类型和数据完整度动态调整模型权重。",
    }
    return {
        "valuation_lens": "目标价计算器",
        "assumptions": result["scenarios"]["base"],
        "cash_flow_confidence": result["confidence"]["level"],
        "cash_flows": {
            "actual_fcf": actual_fcf,
            "normalized_fcf": facts.ocf - facts.capex * 0.8,
            "owner_earnings": owner_earnings,
            "ocf": facts.ocf,
        },
        "yields": {
            "fcf_yield": fcf_yield,
            "ocf_yield": ocf_yield,
            "normalized_fcf_yield": safe_div(facts.ocf - facts.capex * 0.8, facts.market_cap),
            "target_fcf_yield": facts.ten_year_yield + 0.035,
            "cash_flow_anchor_price": safe_div(safe_div(max(owner_earnings, actual_fcf), facts.diluted_shares), facts.ten_year_yield + 0.035),
        },
        "sanity_metrics": {
            "price_to_sales": safe_div(facts.market_cap, facts.revenue),
            "price_to_actual_fcf": safe_div(facts.market_cap, actual_fcf),
            "price_to_owner_earnings": safe_div(facts.market_cap, owner_earnings),
            "operating_margin": facts.operating_margin,
            "sbc_to_revenue": safe_div(facts.sbc, facts.revenue),
            "capex_to_ocf": safe_div(facts.capex, facts.ocf),
        },
        "cash_flow_fair_value_center": result["intrinsic_value_3y"]["base"],
        "fair_value_center": target["base"],
        "fair_value_range": {"low": target["range_low"], "high": target["range_high"]},
        "margin_of_safety_buy_price": {"single": target["range_low"], "low": target["bear"] * 0.85, "high": target["bear"] * 0.95},
        "overvalued_price": target["bull"] * 1.08,
        "judgement": judgement_map.get(result["rating"], result["rating"]),
        "v3_summary": {
            "style": result["company_type"],
            "style_label": result["company_state"],
            "conservative_range": {"low": target["bear"] * 0.90, "base": target["bear"], "high": target["base"] * 0.92},
            "market_reasonable_range": {"low": target["range_low"], "base": target["base"], "high": target["range_high"]},
            "optimistic_growth_range": {"low": target["base"], "base": target["bull"], "high": target["bull"] * 1.12},
            "buy_range": {"low": target["bear"] * 0.85, "high": target["bear"] * 0.95},
            "high_risk_overvaluation_price": target["bull"] * 1.08,
            "model_consistency": model_consistency,
            "forward_inputs": {
                "forward_eps_estimate": result["forward_estimates"]["eps_next_year"]["value"],
                "forward_revenue": result["forward_estimates"]["revenue_next_year"]["value"],
                "forward_ebitda_proxy": result["forward_estimates"]["ebitda_next_year"]["value"],
                "projection_years": 1,
            },
        },
        "valuation_models": [
            {
                "key": item["model"],
                "label": item["label"],
                "low": item["bear"],
                "base": item["base"],
                "high": item["bull"],
                "weight": item["weight"],
                "explanation": item["weight_reason"],
            }
            for item in result["model_outputs"]
        ],
        "reverse_dcf": {
            "implied_5y_growth": result["reverse_expectations"].get("implied_revenue_cagr_5y"),
            "plain_language": result["reverse_expectations"].get("plain_language", ""),
            "requires_bull_case": result["reverse_expectations"].get("difficulty") in {"aggressive", "very_aggressive"},
            "is_capped": False,
        },
        "terminal_dependency": result["dcf"]["base"]["terminal_dependency"],
        "plain_language": {
            **result["plain_language"],
            "sanity_check": (
                f"按当前市值计算，P/FCF 约 {safe_div(facts.market_cap, actual_fcf):.1f}x，"
                f"P/S 约 {safe_div(facts.market_cap, facts.revenue):.1f}x。"
                f"系统估算或读取的 forward PE 输入已纳入目标价模型，模型权重会按数据完整度重新归一化，"
                f"不需要你自己判断模型冲突。"
            ),
            "model_consistency": model_consistency["plain_language"],
            "most_sensitive": "未来收入增速、利润率和 CAPEX 回报是否兑现",
            "watch": [
                "forward 共识数据是否需要手动更新。",
                "成长 CAPEX 是否能转化为未来收入和现金流。",
                "当前价格隐含预期是否已经过于乐观。",
            ],
        },
        "formula_notes": {
            "actual_fcf": "实际 FCF = OCF - CAPEX。",
            "owner_earnings": "Owner Earnings = OCF - 维护性 CAPEX - SBC 调整。",
            "dcf": "V4.0 使用三阶段 FCFF DCF，并在 CAPEX 激增时拆出成长性开支。",
            "reverse_dcf": "反向 DCF 反推当前股价要求未来做到什么。",
        },
    }


def run_valuation(facts_dict: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    scenario = SimpleNamespace(
        bear=SimpleNamespace(revenue_cagr_5y=overrides.get("bear_growth"), probability=overrides.get("bear_probability")),
        base=SimpleNamespace(
            revenue_cagr_5y=overrides.get("base_growth"),
            discount_rate=overrides.get("discount_rate"),
            terminal_growth=overrides.get("terminal_growth"),
            probability=overrides.get("base_probability"),
        ),
        bull=SimpleNamespace(revenue_cagr_5y=overrides.get("bull_growth"), probability=overrides.get("bull_probability")),
        consensus=overrides.get("consensus"),
        horizon=overrides.get("horizon", "12m"),
        use_dynamic_multiples=overrides.get("use_dynamic_multiples", True),
        use_reverse_dcf=overrides.get("use_reverse_dcf", True),
        use_capex_split=overrides.get("use_capex_split", True),
        manual_overrides={
            key: value
            for key, value in overrides.items()
            if key
            in {
                "operating_margin_terminal",
                "fcf_margin_terminal",
                "exit_pe",
                "exit_ev_ebitda",
                "exit_ev_sales",
                "maintenance_capex",
                "maintenance_capex_ratio",
                "peer_snapshot",
                "multiples_history",
            }
        },
    )
    return run_target_price_calculator(facts_dict, scenario)
