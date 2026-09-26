"""Parse IRS Form 990 / 990-EZ e-file XML into a flat dict of the fields we use."""
import re
import xml.etree.ElementTree as ET

def _strip(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag

def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def parse_990(xml_bytes):
    root = ET.fromstring(xml_bytes)
    for el in root.iter():
        el.tag = _strip(el.tag)
    hdr = root.find("ReturnHeader")
    out = {}
    g = lambda path, base=root: (base.findtext(path) if base is not None else None)
    out["return_type"] = g("ReturnHeader/ReturnTypeCd")
    out["tax_period_begin"] = g("ReturnHeader/TaxPeriodBeginDt")
    out["tax_period_end"] = g("ReturnHeader/TaxPeriodEndDt")
    out["ein"] = g("ReturnHeader/Filer/EIN")
    out["filer_name"] = g("ReturnHeader/Filer/BusinessName/BusinessNameLine1Txt")
    out["filer_city"] = g("ReturnHeader/Filer/USAddress/CityNm")
    out["filer_state"] = g("ReturnHeader/Filer/USAddress/StateAbbreviationCd")
    out["filer_street"] = g("ReturnHeader/Filer/USAddress/AddressLine1Txt")
    out["filer_zip"] = g("ReturnHeader/Filer/USAddress/ZIPCd")
    out["return_ts"] = g("ReturnHeader/ReturnTs")
    rd = root.find("ReturnData")
    f = rd.find("IRS990") if rd is not None else None
    if f is None:
        ez = rd.find("IRS990EZ") if rd is not None else None
        if ez is None:
            return out
        out["form"] = "990EZ"
        out["amended"] = ez.findtext("AmendedReturnInd") is not None
        out["total_revenue"] = _num(ez.findtext("TotalRevenueAmt"))
        out["contributions_grants"] = _num(ez.findtext("ContributionsGiftsGrantsEtcAmt"))
        out["program_service_revenue"] = _num(ez.findtext("ProgramServiceRevenueAmt"))
        out["total_expenses"] = _num(ez.findtext("TotalExpensesAmt"))
        out["net_assets_eoy"] = _num(ez.findtext("NetAssetsOrFundBalancesEOYAmt"))
        out["total_assets_eoy"] = _num(ez.findtext("Form990TotalAssetsGrp/EOYAmt"))
        out["total_liabilities_eoy"] = _num(ez.findtext("SumOfTotalLiabilitiesGrp/EOYAmt"))
        out["salaries_etc"] = _num(ez.findtext("SalariesOtherCompEmplBnftAmt"))
        officers = []
        for o in ez.findall("OfficerDirectorTrusteeEmplGrp"):
            officers.append({"name": o.findtext("PersonNm") or o.findtext("BusinessName/BusinessNameLine1Txt"),
                             "title": o.findtext("TitleTxt"),
                             "comp_org": _num(o.findtext("CompensationAmt")) or 0,
                             "comp_related": 0,
                             "comp_other": _num(o.findtext("EmployeeBenefitProgramAmt")) or 0,
                             "hours": _num(o.findtext("AverageHrsPerWkDevotedToPosRt"))})
        out["officers"] = officers
        return out
    out["form"] = "990"
    out["amended"] = f.findtext("AmendedReturnInd") is not None
    out["website"] = f.findtext("WebsiteAddressTxt")
    out["mission"] = (f.findtext("ActivityOrMissionDesc") or f.findtext("MissionDesc") or "")[:500]
    out["formation_year"] = f.findtext("FormationYr")
    out["total_employees"] = _num(f.findtext("TotalEmployeeCnt"))
    out["total_volunteers"] = _num(f.findtext("TotalVolunteersCnt"))
    out["total_revenue"] = _num(f.findtext("CYTotalRevenueAmt")) or _num(f.findtext("TotalRevenueGrp/TotalRevenueColumnAmt"))
    out["total_revenue_py"] = _num(f.findtext("PYTotalRevenueAmt"))
    out["contributions_grants"] = _num(f.findtext("CYContributionsGrantsAmt"))
    out["government_grants"] = _num(f.findtext("GovernmentGrantsAmt"))  # Part VIII line 1e
    out["program_service_revenue"] = _num(f.findtext("CYProgramServiceRevenueAmt")) or _num(f.findtext("TotalProgramServiceRevenueAmt"))
    out["investment_income"] = _num(f.findtext("CYInvestmentIncomeAmt"))
    out["other_revenue"] = _num(f.findtext("CYOtherRevenueAmt"))
    out["total_expenses"] = _num(f.findtext("CYTotalExpensesAmt")) or _num(f.findtext("TotalFunctionalExpensesGrp/TotalAmt"))
    out["program_expenses"] = _num(f.findtext("TotalFunctionalExpensesGrp/ProgramServicesAmt"))
    out["mgmt_general_expenses"] = _num(f.findtext("TotalFunctionalExpensesGrp/ManagementAndGeneralAmt"))
    out["fundraising_expenses"] = _num(f.findtext("TotalFunctionalExpensesGrp/FundraisingAmt"))
    out["grants_paid"] = _num(f.findtext("CYGrantsAndSimilarPaidAmt"))
    out["salaries_etc"] = _num(f.findtext("CYSalariesCompEmpBnftPaidAmt"))
    out["officer_comp_partix"] = _num(f.findtext("CompCurrentOfcrDirectorsGrp/TotalAmt"))
    out["total_assets_eoy"] = _num(f.findtext("TotalAssetsEOYAmt"))
    out["total_liabilities_eoy"] = _num(f.findtext("TotalLiabilitiesEOYAmt"))
    out["net_assets_eoy"] = _num(f.findtext("NetAssetsOrFundBalancesEOYAmt"))
    out["net_assets_boy"] = _num(f.findtext("NetAssetsOrFundBalancesBOYAmt"))
    out["cash_eoy"] = _num(f.findtext("CashNonInterestBearingGrp/EOYAmt"))
    out["savings_eoy"] = _num(f.findtext("SavingsAndTempCashInvstGrp/EOYAmt"))
    out["unrestricted_na_eoy"] = _num(f.findtext("NoDonorRestrictionNetAssetsGrp/EOYAmt")) or _num(f.findtext("UnrestrictedNetAssetsGrp/EOYAmt"))
    out["n_comp_over_100k"] = _num(f.findtext("IndivRcvdGreaterThan100KCnt"))
    out["n_contractors_over_100k"] = _num(f.findtext("CntrctRcvdGreaterThan100KCnt"))
    officers = []
    for o in f.findall("Form990PartVIISectionAGrp"):
        officers.append({"name": o.findtext("PersonNm") or o.findtext("BusinessName/BusinessNameLine1Txt"),
                         "title": o.findtext("TitleTxt"),
                         "comp_org": _num(o.findtext("ReportableCompFromOrgAmt")) or 0,
                         "comp_related": _num(o.findtext("ReportableCompFromRltdOrgAmt")) or 0,
                         "comp_other": _num(o.findtext("OtherCompensationAmt")) or 0,
                         "hours": _num(o.findtext("AverageHoursPerWeekRt")),
                         "officer": o.findtext("OfficerInd") is not None,
                         "key_employee": o.findtext("KeyEmployeeInd") is not None,
                         "highest_comp": o.findtext("HighestCompensatedEmployeeInd") is not None,
                         "former": o.findtext("FormerOfcrDirectorTrusteeInd") is not None,
                         "trustee": o.findtext("IndividualTrusteeOrDirectorInd") is not None})
    out["officers"] = officers
    contractors = []
    for c in f.findall("ContractorCompensationGrp"):
        contractors.append({"name": c.findtext("ContractorName/BusinessName/BusinessNameLine1Txt") or c.findtext("ContractorName/PersonNm"),
                            "services": c.findtext("ServicesDesc"),
                            "amount": _num(c.findtext("CompensationAmt"))})
    out["contractors"] = contractors
    # Schedule I: grants to domestic organizations (subgrants / pass-through)
    si = rd.find("IRS990ScheduleI")
    grants = []
    if si is not None:
        for r in si.findall("RecipientTable"):
            grants.append({"name": r.findtext("RecipientBusinessName/BusinessNameLine1Txt") or r.findtext("RecipientNameBusiness/BusinessNameLine1Txt"),
                           "ein": r.findtext("RecipientEIN"),
                           "city": r.findtext("USAddress/CityNm"),
                           "state": r.findtext("USAddress/StateAbbreviationCd"),
                           "cash": _num(r.findtext("CashGrantAmt")),
                           "noncash": _num(r.findtext("NonCashAssistanceAmt")),
                           "purpose": r.findtext("PurposeOfGrantTxt")})
    out["schedule_i_grants"] = grants
    # Schedule L (transactions with interested persons) presence flag
    out["has_schedule_l"] = rd.find("IRS990ScheduleL") is not None
    # Part IV / VI governance flags
    out["conflict_policy"] = f.findtext("ConflictOfInterestPolicyInd")
    out["whistleblower_policy"] = f.findtext("WhistleblowerPolicyInd")
    out["audited_fs"] = f.findtext("FSAuditedInd")
    out["single_audit"] = f.findtext("FederalGrantAuditRequiredInd")
    out["material_diversion"] = f.findtext("MaterialDiversionOrMisuseInd")
    return out
