"""
Admin utilities.
"""

from aiogram.fsm.context import FSMContext


async def clear_state_preserve_admin_token(state: FSMContext) -> None:
    """
    Clear FSM state but preserve admin_session_token.
    
    Args:
        state: FSM context
    """
    data = await state.get_data()
    token = data.get("admin_session_token")
    
    await state.clear()
    
    if token:
        await state.update_data(admin_session_token=token)

