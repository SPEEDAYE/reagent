# util/validate_format.py — Use case JSON schema validator.
#
# validate_use_case_format(use_cases) → (bool, str)
#   Checks: list of dicts with exactly these keys:
#     use_case_name (str), primary_actor (str), secondary_actor (list[str]),
#     trigger (str), preconditions (list[str]), postconditions (list[str]),
#     main_flow (list[str]), alternative_flows (list[str]),
#     exception_flows (list[str]), priority (str),
#     business_rules (list[str]), assumptions (list[str]),
#     other_constraints (list[str])
#   Returns (True, "OK") or (False, error_message).
def validate_use_case_format(use_cases):
    """
    校验用户用例输出是否符合严格的 Use Case 格式规范。
    
    返回:
        (bool, str)
        - True, "OK" 表示通过校验
        - False, 错误信息字符串
    """

    required_schema = {
        "use_case_name": str,
        "primary_actor": str,
        "secondary_actor": list,
        "use_case_description": str,
        "trigger": str,
        "preconditions": list,
        "postconditions": list,
        "main_flow": list,
        "alternative_flows": list,
        "exception_flows": list,
        "priority": str,
        "business_rules": list,
        "assumptions": list,
        "other_constraints": list
    }

    # 1️⃣ 顶层必须是 list
    if not isinstance(use_cases, list):
        return False, "Top-level structure must be a list."

    if len(use_cases) == 0:
        return False, "Use case list must not be empty."

    # 2️⃣ 每个元素必须是 dict
    for idx, use_case in enumerate(use_cases):
        if not isinstance(use_case, dict):
            return False, f"Use case at index {idx} is not a dictionary."

        # 3️⃣ 字段必须完全一致（不多不少）
        keys = set(use_case.keys())
        required_keys = set(required_schema.keys())

        if keys != required_keys:
            missing = required_keys - keys
            extra = keys - required_keys
            return False, (
                f"Use case at index {idx} has invalid keys. "
                f"Missing: {missing}, Extra: {extra}"
            )

        # 4️⃣ 字段类型校验
        for field, expected_type in required_schema.items():
            value = use_case[field]

            if not isinstance(value, expected_type):
                return False, (
                    f"Field '{field}' in use case at index {idx} "
                    f"must be of type {expected_type.__name__}."
                )

            # 5️⃣ 所有 list 字段的元素必须是字符串
            if expected_type is list:
                for item_idx, item in enumerate(value):
                    if not isinstance(item, str):
                        return False, (
                            f"Field '{field}' in use case at index {idx} "
                            f"contains non-string element at position {item_idx}."
                        )

    return True, "OK"
