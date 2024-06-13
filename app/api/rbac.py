from typing import List

from fastapi import Depends, HTTPException

from app.api.deps import get_current_account, get_current_active_account
from app.models import Account, account


class RoleCheck:
    def __init__(self, roles: List[account.AccountRole]) -> None:
        self.required_roles = roles

    def __call__(self, account: Account = Depends(get_current_account)) -> bool:
        if account.role not in self.required_roles:
            raise HTTPException(status_code=401, detail="Not authorized")
        return True


class PermissionCheck:
    def __init__(self, permissions: List[str]) -> None:
        self.required_permissions = permissions

    def __call__(self, account: Account = Depends(get_current_active_account)) -> bool:
        for r_perm in self.required_permissions:
            if r_perm not in account.permissions:
                raise HTTPException(status_code=401, detail="Not authorized")
        return True
