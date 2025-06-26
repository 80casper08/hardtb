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

# Flask сервер для Render
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

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
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[button] for button in buttons],
        resize_keyboard=True
    )
    return keyboard

@dp.message(F.text.in_(sections.keys()))
async def start_quiz(message: types.Message, state: FSMContext):
    category = message.text
    await state.set_state(QuizState.category)
    await state.update_data(category=category, question_index=0, selected_options=[])
    await send_question(message, state)

async def send_question(message_or_callback, state: FSMContext):
    data = await state.get_data()
    questions = sections[data["category"]]
    index = data["question_index"]

    if index >= len(questions):
        correct = 0
        for i, q in enumerate(questions):
            correct_answers = {j for j, (_, is_correct) in enumerate(q["options"]) if is_correct}
            user_selected = set(data["selected_options"][i])
            if correct_answers == user_selected:
                correct += 1
        percent = round(correct / len(questions) * 100)
        result = f"✅ Правильних відповідей: {correct} з {len(questions)} ({percent}%)"
        await message_or_callback.answer(result, reply_markup=main_keyboard())
        await state.clear()
        return

    question = questions[index]
    text = question["text"]
    options = list(enumerate(question["options"]))
    random.shuffle(options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (label, _) in options:
        prefix = "✅ " if i in selected else "▫️ "
        buttons.append([InlineKeyboardButton(text=prefix + label, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await message_or_callback.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("opt_"))
async def toggle_option(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    if index in selected:
        selected.remove(index)
    else:
        selected.add(index)
    await state.update_data(temp_selected=selected)
    await send_question(callback, state)

@dp.callback_query(F.data == "confirm")
async def confirm_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("temp_selected", set())
    selected_options = data.get("selected_options", [])
    selected_options.append(list(selected))
    await state.update_data(
        selected_options=selected_options,
        question_index=data["question_index"] + 1,
        temp_selected=set()
    )
    await send_question(callback, state)

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
