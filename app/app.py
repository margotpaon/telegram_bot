import os
import logging
import random
import sqlite3
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Load environment variables from the .env file
load_dotenv()

# Get bot token from the .env file
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Initialize the bot and the dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Connect to the SQLite database
conn = sqlite3.connect('user_points.db')
cursor = conn.cursor()

# Create the 'points' table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS points (
                  user_id INTEGER PRIMARY KEY,
                  points INTEGER)''')
# Create the 'admins' table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
                  user_id INTEGER PRIMARY KEY)''')
conn.commit()

# Command /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    logging.info(f"Command /start received from {message.from_user.id}")
    welcome_message = (
        "Hello! Here with me you can open boxes and earn more points:\n\n"
        "/points - Check how many points you have.\n"
        "/add_points [quantity] - Add points to your account.\n"
        "/open_box - Open a box of random points.\n"
        "/reset_points - Reset your points to zero.\n\n"
        "Please use these commands to interact with me."
    )
    await message.reply(welcome_message)

# Command to check the user's points
@dp.message_handler(commands=['points'])
async def check_points(message: types.Message):
    logging.info(f"Command /points received from {message.from_user.id}")
    user_id = message.from_user.id
    cursor.execute("SELECT points FROM points WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    points = row[0] if row else 0
    await message.reply(f"You have {points} points.")

# Command to add points to the user
@dp.message_handler(commands=['add_points'])
async def add_points(message: types.Message):
    logging.info(f"Command /add_points received from {message.from_user.id}")
    user_id = message.from_user.id
    if is_admin(user_id):
        # Extract the number of points from the command
        try:
            points_to_add = int(message.text.split()[1])
            if points_to_add < 0:
                raise ValueError("Points to be added must be positive.")
            cursor.execute("INSERT OR REPLACE INTO points (user_id, points) VALUES (?, COALESCE((SELECT points FROM points WHERE user_id=?), 0) + ?)", (user_id, user_id, points_to_add))
            conn.commit()
            await message.reply(f"{points_to_add} points have been added to your account.")
        except (IndexError, ValueError) as e:
            logging.error(f"Error adding points: {e}")
            await message.reply("Please specify the number of points to be added.")
    else:
        await message.reply("You do not have permission to execute this command.")

# Command to open a box of random points
@dp.message_handler(commands=['open_box'])
async def open_box(message: types.Message):
    logging.info(f"Command /open_box received from {message.from_user.id}")
    user_id = message.from_user.id
    cursor.execute("SELECT points FROM points WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] >= 10:
        # Simulate a random box
        box_contents = random.choice(["10 points", "20 points", "50 points", "100 points"])
        # Update the user's points after opening the box
        new_points = row[0] - 10
        cursor.execute("UPDATE points SET points = ? WHERE user_id=?", (new_points, user_id))
        conn.commit()
        # Check the user's points again after opening the box
        cursor.execute("SELECT points FROM points WHERE user_id=?", (user_id,))
        updated_row = cursor.fetchone()
        updated_points = updated_row[0] if updated_row else 0
        await message.reply(f"You opened a box and found: {box_contents}.")
        # Add extra points to the user, depending on what was found in the box
        if "10 points" in box_contents:
            extra_points = 10
        elif "20 points" in box_contents:
            extra_points = 20
        elif "50 points" in box_contents:
            extra_points = 50
        elif "100 points" in box_contents:
            extra_points = 100
        # Update the user's points with the extra points
        updated_points += extra_points
        cursor.execute("UPDATE points SET points = ? WHERE user_id=?", (updated_points, user_id))
        conn.commit()
        await message.reply(f"You earned {extra_points} extra points. Now you have {updated_points} points.")
    else:
        await message.reply("You do not have enough points to open a box.")

# Command to reset a user's points
@dp.message_handler(commands=['reset_points'])
async def reset_points(message: types.Message):
    logging.info(f"Command /reset_points received from {message.from_user.id}")
    user_id = message.from_user.id
    if is_admin(user_id):
        try:
            target_user_id = int(message.text.split()[1])
            cursor.execute("UPDATE points SET points = 0 WHERE user_id = ?", (target_user_id,))
            conn.commit()
            await message.reply("User's points have been reset to zero.")
        except (IndexError, ValueError) as e:
            logging.error(f"Error resetting points: {e}")
            await message.reply("Please specify the user's ID.")
    else:
        await message.reply("You do not have permission to execute this command.")

# Function to check if a user is an administrator
def is_admin(user_id):
    cursor.execute("SELECT * FROM admins WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

# Function to get the administrators of a group and save their user_ids in the database
async def get_admins():
    chat_id = CHAT_ID  # Replace with the group or channel ID
    
    # Get information about the chat
    chat = await bot.get_chat(chat_id)
    
    # Get the list of administrators
    admins = [admin.user.id for admin in await chat.get_administrators()]  # Add 'await' here
    
    # Clear the 'admins' table before saving the new data
    cursor.execute("DELETE FROM admins")
    
    # Save the administrator IDs in the database
    for admin_id in admins:
        cursor.execute("INSERT INTO admins (user_id) VALUES (?)", (admin_id,))
    
    conn.commit()
# Schedule the get_admins function to be executed once when the bot starts
async def on_startup(dp):
    await get_admins()

# Start the bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
