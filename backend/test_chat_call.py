import asyncio
from digital_employee.database import get_db
from digital_employee.api.chat import chat, ChatRequest

async def test():
    async for db in get_db():
        try:
            res = await chat(ChatRequest(question='What were the latest facts from the Quality Metrics workstream? And do we have any unapproved WIP current updates?'), db)
            print('SUCCESS')
            print(res.answer)
        except Exception as e:
            import traceback
            traceback.print_exc()
        break
asyncio.run(test())
