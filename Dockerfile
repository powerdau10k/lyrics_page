# Use an Arch Linux base image
FROM archlinux:base-devel

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Update the system, install Python and pip, and clean up pacman cache
RUN pacman -Syu --noconfirm && \
  pacman -S --noconfirm --needed python python-pip && \
  pacman -Scc --noconfirm && \
  rm -rf /var/cache/pacman/pkg/*

# Create a virtual environment using Python's built-in venv module
RUN python -m venv venv

# Upgrade pip within the virtual environment
RUN /app/venv/bin/pip install --upgrade pip

# Set environment variables to use the virtual environment
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy requirements.txt first to leverage Docker's caching mechanism
COPY requirements.txt .

# Install Python dependencies within the virtual environment
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Copy the system prompt files
COPY sysprompt_extract.txt .
COPY sysprompt_summary.txt .
COPY sysprompt_color.txt .
COPY sysprompt_pick_color.txt .

# Copy the .env file
#COPY .env .

# Ensure the templates directory exists
RUN mkdir -p templates

# Copy index.html into the templates directory
COPY index.html templates/

# Create a non-root user and change ownership of /app
RUN useradd -m appuser && \
  chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Define environment variables specific to Quart
ENV QUART_APP=app.py
ENV QUART_RUN_HOST=0.0.0.0

# Set the command to run the Quart application
CMD ["quart", "run", "--host=0.0.0.0", "--port=5000"]
