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
from questions import op_questions, general_questions, lean_questions, qr_questions

# Завантаження токена
load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🔐 ID адміністратора
ADMIN_ID = 710633503  # Замінити при потребі

# Лог-файл
if not os.path.exists("logs.txt"):
    with open("logs.txt", "w", encoding="utf-8") as f:
        f.write("FullName | Username | Дія\n")

def log_action(user: types.User, action: str):
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "—"
    with open("logs.txt", "a", encoding="utf-8") as f:
        f.write(f"{full_name} | {username} | {action}\n")

# Flask сервер
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# Стани
class QuizState(StatesGroup):
    category = State()
    question_index = State()
    selected_options = State()
    score = State()
    answers = State()

# Старт
@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🦺 ОП", "📚 Загальні")
    keyboard.add("⚙️ Lean", "💪QR")
    await message.answer("Оберіть розділ для проходження тесту:", reply_markup=keyboard)
    await state.clear()
    log_action(message.from_user, "Запуск бота / вибір розділу")

# Вибір розділу
@dp.message(F.text.in_({"🦺 ОП", "📚 Загальні", "⚙️ Lean", "💪QR"}))
async def select_category(message: types.Message, state: FSMContext):
    category_map = {
        "🦺 ОП": op_questions,
        "📚 Загальні": general_questions,
        "⚙️ Lean": lean_questions,
        "💪QR": hard_questions,
    }
    questions = category_map[message.text]
    random.shuffle(questions)
    await state.update_data(
        category=message.text,
        question_index=0,
        selected_options=[],
        score=0,
        questions=questions,
        answers=[]
    )
    log_action(message.from_user, f"Почав тест {message.text}")
    await send_question(message.chat.id, questions[0], 0)

async def send_question(chat_id, question, index):
    options = question["options"]
    random.shuffle(options)
    buttons = [
        [InlineKeyboardButton(text=opt[0], callback_data=f"opt_{i}")]
        for i, opt in enumerate(options)
    ]
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = f"{question['text']}"
    await bot.send_message(chat_id, text, reply_markup=markup)

@dp.callback_query(F.data.startswith("opt_"))
async def select_option(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("selected_options", [])
    if idx in selected:
        selected.remove(idx)
    else:
        selected.append(idx)
    await state.update_data(selected_options=selected)
    await callback.answer("Варіант обрано!")

@dp.callback_query(F.data == "confirm")
async def confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]
    questions = data["questions"]
    selected = data.get("selected_options", [])
    current_question = questions[index]
    correct_indexes = [i for i, opt in enumerate(current_question["options"]) if opt[1]]

    is_correct = set(selected) == set(correct_indexes)
    score = data["score"] + (1 if is_correct else 0)
    answer_summary = {
        "text": current_question["text"],
        "selected": [current_question["options"][i][0] for i in selected],
        "correct": [opt[0] for opt in current_question["options"] if opt[1]],
        "is_correct": is_correct
    }
    answers = data["answers"]
    answers.append(answer_summary)

    if index + 1 >= len(questions):
        await state.clear()
        text = f"✅ Тест завершено!\n\nПравильних відповідей: {score} з {len(questions)}"
        buttons = [
            [InlineKeyboardButton(text="🔁 Пройти ще раз", callback_data="restart")],
            [InlineKeyboardButton(text="📋 Детальна інформація", callback_data="details")]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.answer(text, reply_markup=markup)
        log_action(callback.from_user, f"Завершив тест ({score}/{len(questions)})")
        await state.update_data(answers=answers)
    else:
        await state.update_data(
            question_index=index + 1,
            selected_options=[],
            score=score,
            answers=answers
        )
        await send_question(callback.message.chat.id, questions[index + 1], index + 1)
    await callback.answer()

@dp.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery, state: FSMContext):
    await start(callback.message, state)

@dp.callback_query(F.data == "details")
async def details(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    text = "📋 *Результати тесту:*\n\n"
    for ans in answers:
        if not ans["is_correct"]:
            text += f"❌ *{ans['text']}*\n"
            text += f"Ваша відповідь: {', '.join(ans['selected']) or '—'}\n"
            text += f"Правильна відповідь: {', '.join(ans['correct'])}\n\n"
    if text.strip() == "📋 *Результати тесту:*":
        text += "Усі відповіді правильні! 🎉"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()
