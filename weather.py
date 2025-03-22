from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import logging
import sys
import uuid
import datetime
import os
import traceback
import json
from contextvars import ContextVar

# Context variables for request-specific information
correlation_id: ContextVar[str] = ContextVar('correlation_id', default=str(uuid.uuid4()))
request_id: ContextVar[str] = ContextVar('request_id', default=str(uuid.uuid4()))
user_id: ContextVar[str] = ContextVar('user_id', default="unknown")  # Consider setting this from authentication context

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            'timestamp': datetime.datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': correlation_id.get(),
            'request_id': request_id.get(),
            'user_id': user_id.get(),
            'file': f"{record.filename}:{record.lineno}",
            'function': record.funcName,
            'process': record.process,
            'thread': record.threadName,
            'environment': os.getenv("ENV", "development"),  # Use ENV var, default to development
            'app_version': os.getenv("APP_VERSION", "0.1.0"), # Use APP_VERSION env var
            'host': os.getenv("HOSTNAME", "localhost"),  # Use HOSTNAME env var
            'duration': getattr(record, 'duration', '0.0s'),
        }
        if record.exc_info:
            log_record['error_details'] = ''.join(traceback.format_exception(*record.exc_info))  # Format the stack trace
        elif hasattr(record, 'error_details'):
            log_record['error_details'] = record.error_details
        return json.dumps(log_record)

# Configure named logger
logger = logging.getLogger("WeatherService") # More specific service name
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))  # Respect LOG_LEVEL env var, default to INFO

# Clear existing handlers to avoid duplication (important for reloading)
if logger.hasHandlers():
    logger.handlers.clear()


# Console handler with JSON formatter
console_handler = logging.StreamHandler(sys.stderr)

# Use JSON formatter in production, otherwise use a more readable format
if os.getenv("ENV") == "production":
    console_handler.setFormatter(JSONFormatter())
else:
    # Example of a simpler, more readable formatter for development
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    console_handler.setFormatter(formatter)  # Replace with your pretty formatter if desired

logger.addHandler(console_handler)

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# Helper function
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    req_id = str(uuid.uuid4()) #Generate unique request ID
    request_id.set(req_id)
    start_time = datetime.datetime.now()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    try:
        logger.debug(f"Making request to: {url}", extra={"request_id":req_id})
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            duration = datetime.datetime.now() - start_time
            logger.info(f"Request to {url} successful. Status code: {response.status_code}",
                        extra={"duration": f"{duration.total_seconds():.6f}s", "request_id":req_id})
            return response.json()
    except httpx.HTTPStatusError as e:
        duration = datetime.datetime.now() - start_time
        logger.error(f"HTTP error occurred: {e}", exc_info=True,
                     extra={"error_code": str(e.response.status_code), "duration": f"{duration.total_seconds():.6f}s", "request_id":req_id})
        return None
    except httpx.TimeoutException as e:
        duration = datetime.datetime.now() - start_time
        logger.error(f"Timeout error occurred: {e}", exc_info=True,
                     extra={"duration": f"{duration.total_seconds():.6f}s", "request_id":req_id})
        return None
    except Exception as e:
        duration = datetime.datetime.now() - start_time
        logger.exception(f"An unexpected error occurred: {e}",
                          extra={"duration": f"{duration.total_seconds():.6f}s", "request_id":req_id})
        return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

# Implementing tool execution
@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    start_time = datetime.datetime.now()
    corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    try:
        logger.info(f"Getting alerts for state: {state}", extra={"correlation_id":corr_id})
        url = f"{NWS_API_BASE}/alerts/active/area/{state}"
        data = await make_nws_request(url)

        if not data or "features" not in data:
            logger.warning(f"No data or 'features' key found for state: {state}", extra={"correlation_id":corr_id})
            return "Unable to fetch alerts or no alerts found."

        if not data["features"]:
            logger.info(f"No active alerts found for state: {state}", extra={"correlation_id":corr_id})
            return "No active alerts for this state."

        alerts = [format_alert(feature) for feature in data["features"]]
        duration = datetime.datetime.now() - start_time
        logger.info(f"Successfully fetched and formatted alerts for state: {state}",
                    extra={"duration": f"{duration.total_seconds():.6f}s", "correlation_id":corr_id})
        return "\n---\n".join(alerts)
    except Exception as e:
        duration = datetime.datetime.now() - start_time
        logger.exception(f"Error getting alerts for state: {state}", exc_info=True,
                          extra={"duration": f"{duration.total_seconds():.6f}s", "correlation_id":corr_id})
        return "An error occurred while fetching alerts."

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    start_time = datetime.datetime.now()
    corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    try:
        logger.info(f"Getting forecast for latitude: {latitude}, longitude: {longitude}", extra={"correlation_id":corr_id})
        # First get the forecast grid endpoint
        points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
        data = await make_nws_request(points_url)

        if not data:
            logger.warning(f"Unable to fetch forecast data for latitude: {latitude}, longitude: {longitude}", extra={"correlation_id":corr_id})
            return "Unable to fetch forecast data for this location."

        # Get the forecast URL from the points response
        forecast_url = data["properties"]["forecast"]
        forecast_data = await make_nws_request(forecast_url)

        if not forecast_data:
            logger.warning(f"Unable to fetch detailed forecast for latitude: {latitude}, longitude: {longitude}", extra={"correlation_id":corr_id})
            return "Unable to fetch detailed forecast."

        # Format the periods into a readable forecast
        periods = forecast_data["properties"]["periods"]
        forecasts = []
        for period in periods[:5]:  # Only show next 5 periods
            forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
            forecasts.append(forecast)
        duration = datetime.datetime.now() - start_time
        logger.info(f"Successfully fetched and formatted forecast for latitude: {latitude}, longitude: {longitude}",
                    extra={"duration": f"{duration.total_seconds():.6f}s", "correlation_id":corr_id})
        return "\n---\n".join(forecasts)
    except Exception as e:
        duration = datetime.datetime.now() - start_time
        logger.exception(f"Error getting forecast for latitude: {latitude}, longitude: {longitude}", exc_info=True,
                          extra={"duration": f"{duration.total_seconds():.6f}s", "correlation_id":corr_id})
        return "An error occurred while fetching forecast."

# Running the server
if __name__ == "__main__":
    # Initialize and run the server
    logger.info("Starting the MCP server...",extra={"correlation_id": str(uuid.uuid4())}) #Starting correlation ID
    mcp.run(transport='stdio')
    logger.info("MCP server stopped.",extra={"correlation_id": str(uuid.uuid4())})
