from services.procurement_reference_registry import ProcurementReferenceRegistry
from new_model.parser_functions import parse_okpd_entries, parse_ktry_entries
from typing import List

def get_regestry_response_okpd_ktry(plan_points_use: List[str], REGISTRY_DIR: str) -> List[str]:
    registry = ProcurementReferenceRegistry(REGISTRY_DIR)
    parsed_okpd = parse_okpd_entries(plan_points_use[0])
    parsed_ktry = parse_ktry_entries(plan_points_use[1])

    res_ktry = []
    res_okpd = []

    for entry in parsed_ktry:
        try:
            res = registry.check_ktru(entry["ktru_code"], entry["name"])
            res_ktry.append(res.message)
        except Exception:
            res_ktry.append(
                f"Возникли проблемы с доступом к сайту при проверке КТРУ {entry['ktru_code']}."
            )

    for entry in parsed_okpd:
        try:
            res = registry.check_okpd2(entry["okpd2"], entry["name"])
            res_okpd.append(res.message)
        except Exception:
            res_okpd.append(
                f"Возникли проблемы с доступом к сайту при проверке ОКПД2 {entry['okpd2']}."
            )
    return res_ktry, res_okpd