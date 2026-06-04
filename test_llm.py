# test_llm.py
from llm_chain import build_llm, get_response
from chat_history import init_memory, add_message

llm = build_llm()
history = init_memory()
history = add_message(history, 'user', 'Say hello in one sentence.')
reply = get_response(llm, history)
print('✅ llm_chain.py OK')
print('Model reply:', reply)