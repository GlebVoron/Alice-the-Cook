from flask import Flask, request, jsonify
import sqlite3
import logging
import uuid

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
    start_time = time.time()
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

        # Быстрый ответ для новых сессий
        if request.json.get('session', {}).get('new', False):
            return jsonify({
                "version": request.json.get("version", "1.0"),
                "session": request.json["session"],
                "response": {
                    "text": "Привет! Я помогу с рецептами. Скажите 'помощь' для списка команд.",
                    "buttons": get_main_suggests(),
                    "end_session": False
                }
            })

        response = {
            "version": request.json.get("version", "1.0"),
            "session": request.json["session"],
            "response": {
                "end_session": False
            }
        }

        handle_dialog(request.json, response)
        logging.info(f'Request processed in {time.time() - start_time:.2f} seconds')
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


def add_recipe(command):
    try:
        parts = command.split(' с ингредиентами ')
        if len(parts) < 2:
            return "Неверный формат команды. Пример: 'Добавь рецепт блины с ингредиентами мука 300г, яйца 2шт, молоко 500мл'"

        recipe_name = parts[0].replace('добавь рецепт ', '').strip()
        ingredients_str = parts[1]

        instructions = "Инструкция не указана"

        conn = sqlite3.connect('alice_recipes.db')
        c = conn.cursor()

        c.execute("SELECT id FROM recipes WHERE name = ?", (recipe_name,))
        if c.fetchone():
            return f"Рецепт '{recipe_name}' уже существует!"

        recipe_id = str(uuid.uuid4())
        c.execute("INSERT INTO recipes (id, name, instructions) VALUES (?, ?, ?)",
                  (recipe_id, recipe_name, instructions))

        ingredients = [ing.strip() for ing in ingredients_str.split(',')]
        for ing in ingredients:
            if not ing:
                continue

            ing_parts = ing.rsplit(' ', 1)
            if len(ing_parts) < 2:
                ing_name = ing
                quantity = ""
            else:
                ing_name, quantity = ing_parts

            c.execute("SELECT id FROM ingredients WHERE name = ?", (ing_name.lower(),))
            ingredient = c.fetchone()

            if not ingredient:
                ingredient_id = str(uuid.uuid4())
                c.execute("INSERT INTO ingredients (id, name) VALUES (?, ?)",
                          (ingredient_id, ing_name.lower()))
            else:
                ingredient_id = ingredient[0]

            c.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity) VALUES (?, ?, ?)",
                      (recipe_id, ingredient_id, quantity))

        conn.commit()
        return f"Рецепт '{recipe_name}' успешно добавлен!"

    except Exception as e:
        logging.error(f"Error adding recipe: {str(e)}")
        return "Произошла ошибка при добавлении рецепта"
    finally:
        conn.close()


def find_recipes_by_ingredients(command):
    try:
        ingredients_str = command.replace('что приготовить из', '').strip()
        user_ingredients = [ing.strip().lower() for ing in ingredients_str.split(',')]

        if not user_ingredients:
            return "Пожалуйста, укажите ингредиенты, например: 'что приготовить из яйца, мука, молоко'"

        conn = sqlite3.connect('alice_recipes.db')
        c = conn.cursor()

        query = """
        SELECT r.name 
        FROM recipes r
        WHERE NOT EXISTS (
            SELECT ri.ingredient_id 
            FROM recipe_ingredients ri
            JOIN ingredients i ON ri.ingredient_id = i.id
            WHERE ri.recipe_id = r.id
            AND i.name NOT IN ({})
        )
        """.format(','.join(['?'] * len(user_ingredients)))

        c.execute(query, user_ingredients)
        recipes = c.fetchall()

        if not recipes:
            return "Не найдено рецептов для указанных ингредиентов. Попробуйте другие ингредиенты."

        recipe_list = "\n- ".join([r[0] for r in recipes])
        return f"Вы можете приготовить:\n- {recipe_list}\n\nСкажите 'как приготовить [название]' для получения инструкций."

    except Exception as e:
        logging.error(f"Error finding recipes: {str(e)}")
        return "Произошла ошибка при поиске рецептов"
    finally:
        conn.close()


def get_recipe_instructions(command):
    try:
        recipe_name = command.replace('как приготовить', '').strip()
        if not recipe_name:
            return "Пожалуйста, укажите название рецепта, например: 'как приготовить блины'"

        conn = sqlite3.connect('alice_recipes.db')
        c = conn.cursor()

        c.execute("SELECT instructions FROM recipes WHERE name = ?", (recipe_name,))
        recipe = c.fetchone()

        if not recipe:
            return f"Рецепт '{recipe_name}' не найден. Попробуйте другой рецепт."

        return f"Рецепт '{recipe_name}':\n\n{recipe[0]}"

    except Exception as e:
        logging.error(f"Error getting recipe: {str(e)}")
        return "Произошла ошибка при получении рецепта"
    finally:
        conn.close()


def get_recipe_ingredients(command):
    try:
        recipe_name = command.replace('что нужно для', '').strip()
        if not recipe_name:
            return "Пожалуйста, укажите название рецепта, например: 'что нужно для блинов'"

        conn = sqlite3.connect('alice_recipes.db')
        c = conn.cursor()

        query = """
        SELECT i.name, ri.quantity 
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        JOIN recipes r ON ri.recipe_id = r.id
        WHERE r.name = ?
        """
        c.execute(query, (recipe_name,))
        ingredients = c.fetchall()

        if not ingredients:
            return f"Рецепт '{recipe_name}' не найден или у него нет ингредиентов."

        ingredients_list = "\n- ".join([f"{ing[0]} {ing[1]}" if ing[1] else ing[0] for ing in ingredients])
        return f"Для приготовления '{recipe_name}' вам понадобится:\n- {ingredients_list}"

    except Exception as e:
        logging.error(f"Error getting ingredients: {str(e)}")
        return "Произошла ошибка при получении списка ингредиентов"
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
