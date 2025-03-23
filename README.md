# Weather MCP Server

## Overview
This repository contains an MCP (Model Context Protocol) server for accessing US weather data from the National Weather Service (NWS) API. The server provides tools to fetch weather alerts and forecasts for locations across the United States.

## Features
- Get weather alerts for any US state using two-letter state codes
- Retrieve detailed weather forecasts by latitude and longitude
- Structured logging with contextual information
- Error handling and timeout management

## Installation
```bash
# Clone the repository
git clone <repository-url>

# Navigate to the directory
cd weather

# Install dependencies (requires Python 3.11+)
pip install -e .
```

## Dependencies
- httpx: For making asynchronous HTTP requests
- mcp: Model Context Protocol library for building MCP servers

## Usage
The server provides two main tools:

### Get Weather Alerts
```python
get_alerts(state: str) -> str
```
- `state`: Two-letter US state code (e.g., CA, NY)
- Returns formatted weather alerts for the specified state

### Get Weather Forecast
```python
get_forecast(latitude: float, longitude: float) -> str
```
- `latitude`: Latitude of the location
- `longitude`: Longitude of the location
- Returns a 5-period weather forecast for the specified coordinates

## Running the Server
```bash
python weather.py
```

The server runs over stdio, making it compatible with MCP clients.

## Development
- Set the `ENV` environment variable to "production" for JSON-formatted logs
- Configure logging level with the `LOG_LEVEL` environment variable

## License
[Specify your license here]
