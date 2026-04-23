from msflib.account.actions import AccountAction, ProfileAction

from ..models import Account, AccountCreate, AccountUpdate, Profile, ProfileCreate, ProfileUpdate

account_action = AccountAction[Account, AccountCreate, AccountUpdate]()

profile_action = ProfileAction[Profile, ProfileCreate, ProfileUpdate]()
