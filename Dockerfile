# Use the official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.38.0-focal

# Set environment variables to avoid prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    libcairo2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*


# Copy the rest of the application code
COPY . /app

# Expose the port your Flask app runs on
EXPOSE 8080

# Command to run your application
CMD ["python", "main.py"]