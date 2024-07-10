from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_cors import CORS
import requests
import openai

app = Flask(__name__)
CORS(app)

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password123'
app.config['MYSQL_DB'] = 'food_delivery_db'

# Initialize MySQL
mysql = MySQL(app)
openai.api_key = ''
weather_api_key = ''

# Define User session dictionary
user_sessions = {}

def get_weather(lat,lon):
    # Sample coordinates for demonstration
    
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api_key}"
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception for HTTP errors
    data = response.json()
    return data['weather'][0]['main']

def get_chat_response(prompt,user_message):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"{user_message} {prompt}         rephrase it with user interaction and your knowledge with recent past messages"}
        ]
    )
    return response['choices'][0]['message']['content'].strip()

@app.route('/chat', methods=['POST'])
def index():
    user_id = request.json.get('user_id')
    user_message = request.json.get('message')
    #location = request.json.get('location', 'Default Location')  # Default location for weather
    lat = request.json.get('lat')
    long = request.json.get('long')
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'state': 'suggest_food', 'data': {'selected_foods': []}}
    
    session = user_sessions[user_id]
    state = session['state']
    
    if state == 'suggest_food':
        weather_condition = get_weather(lat,long)
        session['data']['weather'] = weather_condition
        
        cur = mysql.connection.cursor()
        cur.execute('''SELECT * FROM foods''')
        suitable_foods = cur.fetchall()
        cur.close()
        
        response_text = f"The weather is currently {weather_condition}. Based on the weather, we suggest the following foods:\n"
        
        options = []
        for food in suitable_foods:
            options.append(f"{food[0]} - ${food[1]}")
        
        response_text += "\n".join(options)
        response_text += "\n\nPlease type the food(s) you would like to order, separated by commas."
        session['state'] = 'collect_food_choices'
    
    elif state == 'collect_food_choices':
        selected_food_names = [f.strip() for f in user_message.split(',')]
        
        cur = mysql.connection.cursor()
        placeholders = ', '.join(['%s'] * len(selected_food_names))
        query = f"SELECT * FROM foods WHERE name IN ({placeholders})"
        cur.execute(query, tuple(selected_food_names))
        selected_foods = cur.fetchall()
        cur.close()
        
        if not selected_foods:
            response_text = "Sorry, we couldn't find the selected food items. Please choose from the suggested options."
        else:
            session['data']['selected_foods'] = selected_foods
            session['state'] = 'collect_name'
            response_text = "Great choice! To proceed, please provide your name."
    
    elif state == 'collect_name':
        session['data']['name'] = user_message
        session['state'] = 'collect_address'
        response_text = "Thank you. Could you share your address with us?"
    
    elif state == 'collect_address':
        session['data']['address'] = user_message
        session['state'] = 'collect_phone'
        response_text = "Almost done! Please provide your phone number."
    
    elif state == 'collect_phone':
        session['data']['phone'] = user_message
        
        total_price = 0
        for food in session['data']['selected_foods']:
            total_price += food[1]  # Assuming food[1] is the price
        
        response_text = (f"Thank you, {session['data']['name']}! Here is the information you provided:\n"
                         f"Address: {session['data']['address']}\n"
                         f"Phone: {session['data']['phone']}\n"
                         "Your order summary:\n")
        
        for food in session['data']['selected_foods']:
            response_text += f"{food[0]} - ${food[1]}\n"
        
        response_text += f"Total Price: ${total_price}\n"
        response_text += "We will contact you soon to confirm your order."
        session['state'] = 'complete'
    
    else:
        response_text = "Your order is complete. Thank you!"
    
    # Integrate ChatGPT for natural language understanding and response enhancement
    chatgpt_response = get_chat_response(response_text, user_message)
    final_response = f"{chatgpt_response}"
    
    return jsonify({"response": final_response})

if __name__ == '__main__':
    app.run(debug=True)
