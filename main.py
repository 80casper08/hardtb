import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from questions import op_questions, general_questions, lean_questions, hard_questions

# Завантаження токена
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Ініціалізація бота
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Flask сервер для підтримки Render
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_web).start()

# FSM стани
class QuizState(StatesGroup):
    category = State()
    question_index = State()
    selected_options = State()

# Секції
sections = {
    "🦺 ОП": op_questions,
    "📚 Загальні": general_questions,
    "⚙️ LEAN": lean_questions,
    "💪 Hard Test": hard_questions,
}

user_data = {}

# Кнопки меню
def main_keyboard():
    buttons = [types.KeyboardButton(text=section) for section in sections]
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*buttons)
    return keyboard

@dp.message(F.text.in_(sections.keys()))
async def start_quiz(message: types.Message, state: FSMContext):
    category = message.text
    await state.set_state(QuizState.category)
    await state.update_data(category=category, question_index=0, selected_options=[])
    await send_question(message, state)

async def send_question(message, state: FSMContext):
    data = await state.get_data()
    questions = sections[data["category"]]
    index = data["question_index"]

    if index >= len(questions):
        correct = sum(1 for q, s in zip(questions, data["selected_options"])
                      if set(s) == {i for i, (_, is_correct) in enumerate(q["options"]) if is_correct})
        percent = round(correct / len(questions) * 100)
        result = f"✅ Правильних відповідей: {correct} з {len(questions)} ({percent}%)"
        await message.answer(result, reply_markup=main_keyboard())
        await state.clear()
        return

    question = questions[index]
    text = question["text"]
    options = list(enumerate(question["options"]))
    random.shuffle(options)

    buttons = [
        [InlineKeyboardButton(text=opt[1][0], callback_data=f"{opt[0]}")]
        for opt in options
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data)
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    answer_index = int(callback.data)
    data = await state.get_data()
    selected = data.get("selected_options", [])
    selected.append([answer_index])
    await state.update_data(selected_options=selected, question_index=data["question_index"] + 1)
    await callback.answer()
    await send_question(callback.message, state)

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
