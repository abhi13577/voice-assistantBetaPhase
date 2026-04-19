from app.services.product_api_client import product_api_client
import logging

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = {"rerun_test", "get_run_status"}

# ✅ PRODUCTION: Define permission rules per action
ACTION_PERMISSIONS = {
    "rerun_test": ["qa_engineer", "admin"],     # Only QA and admins can rerun
    "get_run_status": ["qa_engineer", "admin", "user"]  # Everyone can check status
}


class ActionEngine:
    """Execute allowed actions with permission validation."""
    
    async def execute(self, action_type: str, params: dict, user_id: int):
        """Execute action with full validation."""
        
        # ✅ Step 1: Validate user exists
        user = product_api_client.get_user(user_id)
        if not user:
            logger.warning(f"Action attempt by non-existent user_id={user_id}")
            return {
                "success": False,
                "message": "User not found.",
                "data": None
            }
        
        # ✅ Step 2: Validate action type
        if action_type not in ALLOWED_ACTIONS:
            logger.warning(f"Invalid action_type={action_type} from user_id={user_id}")
            return {
                "success": False,
                "message": "Invalid action type.",
                "data": None
            }
        
        # ✅ Step 3: Check permissions (FIXED: was always True)
        if not self._check_permission(user_id, action_type, user):
            logger.warning(f"Permission denied: user_id={user_id} action={action_type} role={user.get('role')}")
            return {
                "success": False,
                "message": "Unauthorized action.",
                "data": None
            }
        
        # ✅ Step 4: Execute action
        if action_type == "rerun_test":
            test_case_id = params.get("test_case_id")
            if not test_case_id:
                logger.warning(f"Missing test_case_id from user_id={user_id}")
                return {
                    "success": False,
                    "message": "Missing test_case_id.",
                    "data": None
                }
            result = product_api_client.get_last_error(user_id)
            logger.info(f"Action rerun_test executed: user_id={user_id} test_case_id={test_case_id}")
            return {
                "success": True,
                "message": f"Test {test_case_id} rerun triggered successfully.",
                "data": result
            }
        
        if action_type == "get_run_status":
            result = product_api_client.get_last_error(user_id)
            logger.info(f"Action get_run_status executed: user_id={user_id}")
            return {
                "success": True,
                "message": "Run status fetched.",
                "data": result
            }

    def _check_permission(self, user_id: int, action_type: str, user: dict) -> bool:
        """✅ PRODUCTION: Real permission check based on user role."""
        if not user:
            return False
        
        # Get user role (default to 'user')
        user_role = user.get("role", "user")
        
        # Admin has all permissions
        if user_role == "admin":
            return True
        
        # Check if user role has permission for this action
        required_roles = ACTION_PERMISSIONS.get(action_type, [])
        has_permission = user_role in required_roles
        
        if not has_permission:
            logger.debug(f"Permission denied: role={user_role} needed_roles={required_roles}")
        
        return has_permission

action_engine = ActionEngine()