import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from questions import op_questions, general_questions, lean_questions, hard_questions

# Завантаження токена
load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ADMIN_ID = 710633503

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run_flask).start()

# FSM
class TestState(StatesGroup):
    q_index = State()
    score = State()
    user_answers = State()
    questions = State()
    mode = State()

# Старт-кнопки
@dp.message(F.text.lower() == "/start")
async def start_handler(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦺 ОП", callback_data="test_op")],
        [InlineKeyboardButton(text="📚 Загальні", callback_data="test_general")],
        [InlineKeyboardButton(text="⚙️ Lean", callback_data="test_lean")],
        [InlineKeyboardButton(text="💪 Hard Test", callback_data="test_hard")],
    ])
    await message.answer("Обери розділ для проходження тесту:", reply_markup=kb)

# Старт тесту
@dp.callback_query(F.data.startswith("test_"))
async def start_test(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.replace("test_", "")
    questions_map = {
        "op": op_questions,
        "general": general_questions,
        "lean": lean_questions,
        "hard": hard_questions
    }
    questions = questions_map[mode]
    await state.set_state(TestState.q_index)
    await state.update_data(q_index=0, score=0, user_answers={}, questions=questions, mode=mode)
    await callback.message.answer(f"✅ Розпочинаємо тест: {mode.upper()}")
    await send_question(callback.message, questions[0], 0, mode)

# Надсилання питання
async def send_question(message: types.Message, question: dict, index: int, mode: str):
    text = f"<b>{index+1}. {question['question']}</b>"
    options = list(enumerate(question["answers"]))
    random.shuffle(options)
    buttons = [
        [InlineKeyboardButton(text=opt[1], callback_data=f"select_{mode}_{index}_{opt[0]}")]
        for opt in options
    ]
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_{mode}_{index}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

# Обробка вибору
@dp.callback_query(F.data.startswith("select_"))
async def handle_selection(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    mode, q_index, ans_index = parts[1], int(parts[2]), int(parts[3])
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    selected = set(user_answers.get(q_index, []))
    selected ^= {ans_index}
    user_answers[q_index] = list(selected)
    await state.update_data(user_answers=user_answers)
    await callback.answer("Вибір оновлено")

# Підтвердження
@dp.callback_query(F.data.startswith("confirm_"))
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    mode, q_index = parts[1], int(parts[2])
    data = await state.get_data()
    questions = data["questions"]
    user_answers = data["user_answers"]
    selected = set(user_answers.get(q_index, []))
    correct = set(questions[q_index]["correct"])

    score = data.get("score", 0)
    if selected == correct:
        score += 1
    await state.update_data(score=score)

    q_index += 1
    if q_index < len(questions):
        await state.update_data(q_index=q_index)
        await send_question(callback.message, questions[q_index], q_index, mode)
    else:
        total = len(questions)
        percent = round(score / total * 100)
        await callback.message.answer(f"🌟 Тест завершено!\nТвій результат: {percent}% ({score} з {total})")
        await send_test_result_with_errors(callback.message, state)
        await state.clear()

# Вивід помилок
async def send_test_result_with_errors(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions = data["questions"]
    user_answers = data["user_answers"]
    wrongs = ""

    for i, q in enumerate(questions):
        correct = set(q["correct"])
        selected = set(user_answers.get(i, []))
        if selected != correct:
            selected_answers = [q["answers"][idx] for idx in selected]
            correct_answers = [q["answers"][idx] for idx in correct]
            wrongs += f"\n❌ <b>{q['question']}</b>\n"
            for idx, ans in enumerate(q["answers"]):
                mark = "☑️" if idx in selected else "🔘"
                wrongs += f"{mark} {ans}\n"
            wrongs += f"<i>Твоя відповідь:</i> {', '.join(selected_answers) if selected_answers else '—'}\n"
            wrongs += f"<i>Правильна відповідь:</i> {', '.join(correct_answers)}\n\n"

    if wrongs:
        await message.answer("<b>Помилки:</b>\n" + wrongs, parse_mode="HTML")
    else:
        await message.answer("✅ Усі відповіді правильні!", parse_mode="HTML")

# Запуск Flask
keep_alive()

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

