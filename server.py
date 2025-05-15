from flask import Flask, request, jsonify
import sqlite3
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def init_db():
    conn = sqlite3.connect('alice_recipes.db')
    c = conn.cursor()


    c.execute('''CREATE TABLE IF NOT EXISTS ingredients
                 (id TEXT PRIMARY KEY,
                  name TEXT UNIQUE)''')

    c.execute('''CREATE TABLE IF NOT EXISTS recipes
                 (id TEXT PRIMARY KEY,
                  name TEXT UNIQUE,
                  instructions TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS recipe_ingredients
                 (recipe_id TEXT,
                  ingredient_id TEXT,
                  quantity TEXT,
                  PRIMARY KEY (recipe_id, ingredient_id),
                  FOREIGN KEY(recipe_id) REFERENCES recipes(id),
                  FOREIGN KEY(ingredient_id) REFERENCES ingredients(id))''')

    conn.commit()
    conn.close()

init_db()

@app.route('/post', methods=['POST'])
def main():
    try:
        logging.info(f'Incoming request: {request.json}')

        if not request.json:
            logging.error('Empty request received')
            return jsonify({
                "response": {
                    "text": "Произошла ошибка. Пустой запрос.",
                    "end_session": False
                },
                "version": "1.0"
            }), 400

        response = {
            "version": request.json.get("version", "1.0"),
            "session": request.json["session"],
            "response": {
                "end_session": False
            }
        }

        handle_dialog(request.json, response)

        logging.info(f'Outgoing response: {response}')
        return jsonify(response)

    except Exception as e:
        logging.error(f'Error processing request: {str(e)}')
        return jsonify({
            "response": {
                "text": "Произошла внутренняя ошибка.",
                "end_session": False
            },
            "version": "1.0"
        }), 500

def handle_dialog(req, res):
    user_id = req['session']['user_id']
    command = req['request']['original_utterance'].lower()

    if req['session']['new']:
        res['response']['text'] = (
            "Привет! Я помогу вам с рецептами. "
            "Вы можете сказать: 'добавить рецепт', 'что приготовить', "
            "'как приготовить [блюдо]' или 'помощь'."
        )
        res['response']['buttons'] = get_main_suggests()
    else:
        if 'помощь' in command or 'что ты умеешь' in command:
            res['response']['text'] = (
                "Я умею работать с рецептами:\n"
                "- Добавлять рецепты: 'Добавь рецепт [название] с ингредиентами [ингредиенты]'\n"
                "- Искать рецепты по ингредиентам: 'Что приготовить из [ингредиенты]'\n"
                "- Показывать рецепт: 'Как приготовить [название]'\n"
                "- Показывать нужные ингредиенты: 'Что нужно для [название]'"
            )
        elif 'привет' in command:
            res['response']['text'] = "Снова здравствуйте! Чем могу помочь с рецептами?"
        elif 'добавь рецепт' in command:
            res['response']['text'] = add_recipe(command)
        elif 'что приготовить из' in command:
            res['response']['text'] = find_recipes_by_ingredients(command)
        elif 'как приготовить' in command:
            res['response']['text'] = get_recipe_instructions(command)
        elif 'что нужно для' in command:
            res['response']['text'] = get_recipe_ingredients(command)
        else:
            res['response']['text'] = "Я не поняла команду. Скажите 'помощь' для списка команд."

        res['response']['buttons'] = get_main_suggests()

def get_main_suggests():
    return [
        {"title": "Добавить рецепт ...", "hide": True},
        {"title": "Что приготовить из ...", "hide": True},
        {"title": "Как приготовить ...", "hide": True},
        {"title": "Что нужно для ...", "hide": True},
        {"title": "Помощь", "hide": True}
    ]