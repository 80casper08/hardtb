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
from questions import op_questions, general_questions, lean_questions, qr_questions, hard_questions

# Завантаження токена
load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🔐 Вкажи свій Telegram ID
ADMIN_ID = 710633503

# Ініціалізація лог-файлу
if not os.path.exists("logs.txt"):
    with open("logs.txt", "w", encoding="utf-8") as f:
        f.write("FullName | Username | Дія\n")

# Flask сервер для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/ping")
def ping():
    return "OK", 200

Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

class QuizState(StatesGroup):
    category = State()
    question_index = State()
    selected_options = State()

sections = {
    "🪺 ОП": op_questions,
    "📚 Загальні": general_questions,
    "⚙️ LEAN": lean_questions,
    "🟞 QR": qr_questions,
    "💪 Hard Test": hard_questions,
}

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
    await state.update_data(category=category, question_index=0, selected_options=[], wrong_answers=[])

    full_name = message.from_user.full_name
    username = message.from_user.username or "немає"

    with open("logs.txt", "a", encoding="utf-8") as f:
        f.write(f"{full_name} | @{username} | Почав тест {category}\n")

    try:
        await bot.send_message(ADMIN_ID, f"👤 {full_name} (@{username}) почав тест {category}")
    except:
        pass

    await send_question(message, state)

async def send_question(message_or_callback, state: FSMContext):
    data = await state.get_data()
    questions = sections[data["category"]]
    index = data["question_index"]

    if index >= len(questions):
        correct = 0
        wrongs = []
        for i, q in enumerate(questions):
            correct_answers = {j for j, (_, is_correct) in enumerate(q["options"]) if is_correct}
            user_selected = set(data["selected_options"][i])
            if correct_answers == user_selected:
                correct += 1
            else:
                wrongs.append({
                    "question": q["text"],
                    "options": q["options"],
                    "selected": list(user_selected),
                    "correct": list(correct_answers)
                })

        await state.update_data(wrong_answers=wrongs)

        percent = round(correct / len(questions) * 100)

        grade = "❌ Погано"
        if percent >= 90:
            grade = "💯 Відмінно"
        elif percent >= 70:
            grade = "👍 Добре"
        elif percent >= 50:
            grade = "👌 Задовільно"

        result = (
            "📊 *Результат тесту:*\n\n"
            f"✅ *Правильних відповідей:* {correct} з {len(questions)}\n"
            f"📈 *Успішність:* {percent}%\n"
            f"🏆 *Оцінка:* {grade}"
        )

        full_name = message_or_callback.from_user.full_name
        username = message_or_callback.from_user.username or "немає"
        category = data["category"]

        with open("logs.txt", "a", encoding="utf-8") as f:
            f.write(f"{full_name} | @{username} | Завершив тест {category} з результатом {correct}/{len(questions)} ({percent}%)\n")

        try:
            await bot.send_message(ADMIN_ID, f"✅ {full_name} (@{username}) завершив тест {category} з результатом {correct}/{len(questions)} ({percent}%)")
        except:
            pass

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Пройти ще раз", callback_data="restart")],
            [InlineKeyboardButton(text="📋 Детальна інформація", callback_data="details")]
        ])

        await message_or_callback.answer(result, reply_markup=keyboard, parse_mode="Markdown")
        return

    question = questions[index]
    text = question["text"]
    options = list(enumerate(question["options"]))
    random.seed(index)
    random.shuffle(options)

    selected = data.get("temp_selected", set())
    buttons = []
    for i, (label, _) in options:
        prefix = "✅ " if i in selected else "▫️ "
        buttons.append([InlineKeyboardButton(text=prefix + label, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if "image" in question:
        image_path = question["image"]
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.answer_photo(types.FSInputFile(image_path))
            await message_or_callback.message.answer(text, reply_markup=keyboard)
        else:
            await message_or_callback.answer_photo(types.FSInputFile(image_path))
            await message_or_callback.answer(text, reply_markup=keyboard)
    else:
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

@dp.callback_query(F.data == "details")
async def show_details(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wrongs = data.get("wrong_answers", [])
    if not wrongs:
        await callback.message.answer("✅ Усі відповіді правильні!")
        return

    for item in wrongs:
        text = f"❌ *{item['question']}*\n"
        for idx, (opt_text, _) in enumerate(item["options"]):
            mark = "☑️" if idx in item["selected"] else "🔘"
            text += f"{mark} {opt_text}\n"
        selected_text = [item["options"][i][0] for i in item["selected"]] if item["selected"] else ["—"]
        correct_text = [item["options"][i][0] for i in item["correct"]]
        text += f"\n_Твоя відповідь:_ {', '.join(selected_text)}"
        text += f"\n_Правильна відповідь:_ {', '.join(correct_text)}"
        await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data == "restart")
async def restart_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Вибери розділ для тесту:", reply_markup=main_keyboard())

@dp.message(F.text == "/myid")
async def get_my_id(message: types.Message):
    await message.answer(f"👤 Твій Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

@dp.message(F.text == "/users")
async def list_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ Недостатньо прав.")
        return

    if not os.path.exists("logs.txt"):
        await message.answer("📄 Логів ще немає.")
        return

    with open("logs.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()[1:]

    users = set()
    for line in lines:
        parts = line.strip().split(" | ")
        if len(parts) >= 2:
            name = parts[0]
            username = parts[1]
            users.add(f"{name} {username}")

    if not users:
        await message.answer("🙃 Користувачів ще немає.")
        return

    sorted_users = sorted(users)
    text = "👥 *Користувачі, які проходили тести:*\n"
    text += "\n".join(f"• {user}" for user in sorted_users)
    await message.answer(text, parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
