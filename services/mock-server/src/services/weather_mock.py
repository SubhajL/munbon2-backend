"""Mock weather service endpoints"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import math
from fastapi import APIRouter, Query, HTTPException

router = APIRouter()

# Thailand weather patterns (simplified)
SEASONAL_PATTERNS = {
    "hot": {"months": [3, 4, 5], "temp_range": (30, 40), "humidity_range": (50, 70), "rain_chance": 0.2},
    "rainy": {"months": [6, 7, 8, 9, 10], "temp_range": (25, 35), "humidity_range": (70, 90), "rain_chance": 0.7},
    "cool": {"months": [11, 12, 1, 2], "temp_range": (20, 30), "humidity_range": (40, 60), "rain_chance": 0.1}
}

def get_season(date: datetime) -> str:
    """Get season based on month"""
    month = date.month
    for season, data in SEASONAL_PATTERNS.items():
        if month in data["months"]:
            return season
    return "hot"  # default

def generate_weather_data(date: datetime, location: str = "default") -> Dict:
    """Generate realistic weather data based on season"""
    season = get_season(date)
    pattern = SEASONAL_PATTERNS[season]
    
    # Add daily variation
    hour_of_day = date.hour
    temp_variation = 5 * math.sin((hour_of_day - 6) * math.pi / 12) if 6 <= hour_of_day <= 18 else -2
    
    base_temp = random.uniform(*pattern["temp_range"])
    temperature = base_temp + temp_variation
    
    # Generate other weather parameters
    humidity = random.uniform(*pattern["humidity_range"])
    wind_speed = random.uniform(5, 25)  # km/h
    
    # Rainfall
    rainfall = 0
    if random.random() < pattern["rain_chance"]:
        rainfall = random.uniform(0.5, 30)  # mm
    
    # ET0 calculation (simplified Penman-Monteith)
    et0 = (0.0023 * (temperature + 17.8) * math.sqrt(abs(temperature - humidity/2)) * 0.408)
    
    return {
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1),
        "rainfall": round(rainfall, 1),
        "wind_speed": round(wind_speed, 1),
        "wind_direction": random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
        "pressure": round(1008 + random.uniform(-5, 5), 1),
        "solar_radiation": round(20 + 10 * math.sin(hour_of_day * math.pi / 24), 1),
        "et0": round(et0, 2),
        "cloud_cover": random.choice(["clear", "partly_cloudy", "cloudy", "overcast"]),
        "visibility": round(10 - (rainfall * 0.3), 1)
    }

@router.get("/api/v1/weather/current")
async def get_current_weather(
    location: Optional[str] = Query("munbon"),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None)
):
    """Get current weather conditions"""
    print(f"[Mock Weather] GET current weather for location: {location}")
    
    current_time = datetime.utcnow()
    weather_data = generate_weather_data(current_time, location)
    
    return {
        "location": location,
        "coordinates": {
            "latitude": lat or 14.8566,
            "longitude": lon or 100.5769
        },
        "timestamp": current_time.isoformat(),
        "current": weather_data,
        "daily_summary": {
            "sunrise": "06:15",
            "sunset": "18:30",
            "max_temp": weather_data["temperature"] + random.uniform(2, 5),
            "min_temp": weather_data["temperature"] - random.uniform(5, 8),
            "rain_probability": SEASONAL_PATTERNS[get_season(current_time)]["rain_chance"] * 100
        }
    }

@router.get("/api/v1/weather/forecast")
async def get_weather_forecast(
    location: Optional[str] = Query("munbon"),
    days: int = Query(7, ge=1, le=14)
):
    """Get weather forecast"""
    print(f"[Mock Weather] GET weather forecast for {days} days")
    
    forecast_data = []
    start_date = datetime.utcnow()
    
    for i in range(days):
        forecast_date = start_date + timedelta(days=i)
        
        # Generate daily forecast
        daily_temps = []
        daily_rainfall = 0
        
        for hour in range(24):
            hour_date = forecast_date.replace(hour=hour)
            hour_weather = generate_weather_data(hour_date, location)
            daily_temps.append(hour_weather["temperature"])
            daily_rainfall += hour_weather["rainfall"] / 24
        
        forecast_data.append({
            "date": forecast_date.date().isoformat(),
            "temperature": {
                "max": round(max(daily_temps), 1),
                "min": round(min(daily_temps), 1),
                "average": round(sum(daily_temps) / len(daily_temps), 1)
            },
            "rainfall": round(daily_rainfall, 1),
            "humidity": round(random.uniform(*SEASONAL_PATTERNS[get_season(forecast_date)]["humidity_range"]), 1),
            "et0": round(random.uniform(3.5, 6.5), 2),
            "rain_probability": round(SEASONAL_PATTERNS[get_season(forecast_date)]["rain_chance"] * 100),
            "conditions": random.choice(["sunny", "partly_cloudy", "cloudy", "rainy", "thunderstorm"])
        })
    
    return {
        "location": location,
        "forecast_days": days,
        "generated_at": datetime.utcnow().isoformat(),
        "forecast": forecast_data
    }

@router.get("/api/v1/weather/historical")
async def get_historical_weather(
    location: str,
    start_date: str,
    end_date: str
):
    """Get historical weather data"""
    print(f"[Mock Weather] GET historical weather from {start_date} to {end_date}")
    
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    if (end - start).days > 365:
        raise HTTPException(status_code=400, detail="Maximum 365 days of historical data allowed")
    
    historical_data = []
    current = start
    
    while current <= end:
        daily_data = {
            "date": current.date().isoformat(),
            "temperature_max": 0,
            "temperature_min": 100,
            "temperature_avg": 0,
            "rainfall_total": 0,
            "humidity_avg": 0,
            "et0_total": 0,
            "solar_radiation_avg": 0,
            "wind_speed_avg": 0
        }
        
        # Generate hourly data for the day
        hourly_temps = []
        hourly_humidity = []
        hourly_et0 = []
        hourly_solar = []
        hourly_wind = []
        
        for hour in range(24):
            hour_date = current.replace(hour=hour)
            weather = generate_weather_data(hour_date, location)
            
            hourly_temps.append(weather["temperature"])
            hourly_humidity.append(weather["humidity"])
            hourly_et0.append(weather["et0"])
            hourly_solar.append(weather["solar_radiation"])
            hourly_wind.append(weather["wind_speed"])
            daily_data["rainfall_total"] += weather["rainfall"] / 24
        
        daily_data["temperature_max"] = round(max(hourly_temps), 1)
        daily_data["temperature_min"] = round(min(hourly_temps), 1)
        daily_data["temperature_avg"] = round(sum(hourly_temps) / 24, 1)
        daily_data["humidity_avg"] = round(sum(hourly_humidity) / 24, 1)
        daily_data["et0_total"] = round(sum(hourly_et0), 2)
        daily_data["solar_radiation_avg"] = round(sum(hourly_solar) / 24, 1)
        daily_data["wind_speed_avg"] = round(sum(hourly_wind) / 24, 1)
        daily_data["rainfall_total"] = round(daily_data["rainfall_total"], 1)
        
        historical_data.append(daily_data)
        current += timedelta(days=1)
    
    return {
        "location": location,
        "period": {
            "start": start_date,
            "end": end_date,
            "days": len(historical_data)
        },
        "data": historical_data,
        "summary": {
            "total_rainfall": round(sum(d["rainfall_total"] for d in historical_data), 1),
            "average_temperature": round(sum(d["temperature_avg"] for d in historical_data) / len(historical_data), 1),
            "total_et0": round(sum(d["et0_total"] for d in historical_data), 2),
            "rain_days": len([d for d in historical_data if d["rainfall_total"] > 0])
        }
    }

@router.get("/api/v1/weather/alerts")
async def get_weather_alerts(
    location: Optional[str] = Query("munbon")
):
    """Get active weather alerts"""
    print(f"[Mock Weather] GET weather alerts for {location}")
    
    alerts = []
    
    # Generate random alerts based on season
    season = get_season(datetime.utcnow())
    
    if season == "rainy" and random.random() > 0.7:
        alerts.append({
            "alert_id": "WA-001",
            "type": "heavy_rain",
            "severity": "warning",
            "title": "Heavy Rain Warning",
            "description": "Heavy rainfall expected in the next 24-48 hours",
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "affected_areas": [location],
            "expected_rainfall": "50-100mm"
        })
    
    if season == "hot" and random.random() > 0.8:
        alerts.append({
            "alert_id": "WA-002",
            "type": "heat_wave",
            "severity": "advisory",
            "title": "Heat Advisory",
            "description": "High temperatures expected, increased ET rates",
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=3)).isoformat(),
            "affected_areas": [location],
            "max_temperature": "40-42°C"
        })
    
    return {
        "location": location,
        "alert_count": len(alerts),
        "alerts": alerts,
        "last_update": datetime.utcnow().isoformat()
    }

@router.get("/api/v1/weather/et0/calculate")
async def calculate_et0(
    temperature: float,
    humidity: float,
    wind_speed: float,
    solar_radiation: float,
    latitude: Optional[float] = Query(14.8566),
    elevation: Optional[float] = Query(100)
):
    """Calculate ET0 using weather parameters"""
    print("[Mock Weather] GET calculate ET0")
    
    # Simplified Penman-Monteith equation
    # This is a mock implementation - real calculation is more complex
    
    # Saturation vapor pressure
    es = 0.6108 * math.exp((17.27 * temperature) / (temperature + 237.3))
    
    # Actual vapor pressure
    ea = es * (humidity / 100)
    
    # Vapor pressure deficit
    vpd = es - ea
    
    # Simplified ET0 calculation
    et0 = (0.408 * solar_radiation + 0.063 * wind_speed * vpd) / (1 + 0.066 * (1 + 0.34 * wind_speed))
    
    return {
        "et0": round(et0, 2),
        "parameters": {
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "solar_radiation": solar_radiation,
            "latitude": latitude,
            "elevation": elevation
        },
        "calculated_at": datetime.utcnow().isoformat(),
        "method": "FAO Penman-Monteith (simplified)"
    }

@router.get("/api/v1/weather/stations")
async def get_weather_stations():
    """Get available weather stations"""
    print("[Mock Weather] GET weather stations")
    
    stations = [
        {
            "station_id": "TMD-001",
            "name": "Munbon Main Station",
            "location": "Munbon Irrigation Project",
            "coordinates": {
                "latitude": 14.8566,
                "longitude": 100.5769
            },
            "elevation": 100,
            "status": "active",
            "sensors": ["temperature", "humidity", "rainfall", "wind", "solar_radiation"],
            "last_update": datetime.utcnow().isoformat()
        },
        {
            "station_id": "TMD-002",
            "name": "Munbon North Station",
            "location": "Northern Canal Area",
            "coordinates": {
                "latitude": 14.8766,
                "longitude": 100.5869
            },
            "elevation": 105,
            "status": "active",
            "sensors": ["temperature", "humidity", "rainfall"],
            "last_update": datetime.utcnow().isoformat()
        }
    ]
    
    return {
        "total_stations": len(stations),
        "active_stations": len([s for s in stations if s["status"] == "active"]),
        "stations": stations,
        "data_provider": "Thai Meteorological Department (Mock)"
    }