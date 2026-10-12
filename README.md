# Signaling Service

Signaling Service is a backend application built with **FastAPI** and **Socket.IO** (ASGI) that handles WebRTC signaling and integrates with an Asterisk SIP Gateway.

## Features

- **WebRTC Signaling:** Handles WebRTC offers, answers, and ICE candidates via Socket.IO.
- **SIP Gateway Integration:** Uses `aiovoip` to bridge WebRTC calls with an Asterisk SIP server.
- **RESTful API:** Provides health checks and user management endpoints via FastAPI.
- **Asynchronous Database:** Uses SQLAlchemy with async drivers (e.g., `asyncmy`) to perform non-blocking database queries.
- **Authentication:** Socket.IO connections are protected with user credentials and tokens.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (optional, for containerization)
- MySQL/MariaDB database
- Asterisk SIP Server

## Installation

### Local Setup

1. **Clone the repository:**
   (Ensure you are in the project root directory)

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install aiovoip
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory and configure your variables (e.g., database URL, Asterisk connection details, JWT secret keys, etc.).

5. **Run the application:**
   ```bash
   python -m app.main
   ```

### Docker Setup

You can also run the application using Docker and Docker Compose.

1. **Build and Run via Docker Compose:**
   ```bash
   docker-compose up --build -d
   ```
   *Note: The container uses `network_mode: "host"`, meaning it will bind to the host's ports (default 8081).*

## Project Structure

- `app/`
  - `controller/` - FastAPI route handlers (e.g., `api.py`, `user_controller.py`).
  - `core/` - Application core settings (e.g., `config.py`, `database.py`).
  - `model/` - Database models.
  - `query/` - Database query abstractions.
  - `service/` - Business logic and external service integrations (e.g., `asterisk_service.py`, `user_service.py`).
  - `socket/` - Socket.IO event handlers and WebRTC logic (`sockets.py`).
  - `test/` - Client and Socket.IO testing scripts.
  - `main.py` - Application entry point (ASGI App wrapper).
- `Dockerfile` - Instructions to build the Docker image.
- `docker-compose.yml` - Docker compose configuration.
- `requirements.txt` - Python dependencies.

## Testing

There are testing scripts available in the `app/test/` directory to help verify Socket.IO connections.

```bash
# Example for testing Socket.IO connection
python app/test/test_sio.py
```
