# Base image: python:3.12-slim is a minimal Python 3.12 image without dev tools
FROM python:3.12-slim

# Set the working directory inside the container — all subsequent commands run here
WORKDIR /app

# Copy requirements first (separate layer) so Docker cache skips pip install
# when only .py files change
COPY requirements.txt .

# Install dependencies; --no-cache-dir keeps the image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source code into the container
COPY . .

# Default command: run the pipeline once and exit (exit 0 on success)
CMD ["python", "main.py"]
