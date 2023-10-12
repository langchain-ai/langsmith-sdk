# Creating a basic MVP (Minimum Viable Product) mock API server in Flask involves defining a few routes and handling requests. Below is a simple example of how you can set up a basic Flask mock API server:

# ```python
from flask import Flask, request, jsonify

app = Flask(__name__)

# Sample data for demonstration purposes
runs = []

# Define a route to create a new run
@app.route('/runs', methods=['POST'])
def create_run():
    data = request.get_json()
    runs.append(data)
    return jsonify(data), 201  # Respond with the created data and a 201 status code

# Define a route to update a run by its ID
@app.route('/runs/<string:run_id>', methods=['PATCH'])
def update_run(run_id):
    data = request.get_json()
    # Find the run with the provided ID and update it
    for run in runs:
        if run.get('run_id') == run_id:
            run.update(data)
            return jsonify(run), 200
    return jsonify({"error": "Run not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0",debug=True)
# ```

# In this example:

# 1. We import Flask and create a Flask application.
# 2. We define a sample list `runs` to store mock run data.
# 3. We create two routes: one for creating a new run (`POST /runs`) and another for updating a run by its ID (`PATCH /runs/<run_id>`).
# 4. When a `POST` request is made to `/runs`, the data is added to the `runs` list, and a JSON response is returned with the created data and a status code of 201 (created).
# 5. When a `PATCH` request is made to `/runs/<run_id>`, the server finds the run with the provided `run_id`, updates it with the data from the request, and returns the updated data with a status code of 200 (OK). If the run is not found, it returns a 404 (Not Found) response.

# To run this mock API server, save the code to a Python file (e.g., `app.py`) and execute it. You can use tools like `curl`, Postman, or any HTTP client to make requests to your mock API.

# This is a very basic mock API server. In a real-world scenario, you would have more features, better error handling, and potentially a database to store and retrieve data.
