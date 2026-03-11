from django import template

register = template.Library()

@register.filter
def calculate_duration(from_stop, to_stop):
    """Calculate duration between two stops"""
    if not from_stop or not to_stop:
        return "N/A"
    
    try:
        from_minutes = from_stop.arrival_time.hour * 60 + from_stop.arrival_time.minute
        to_minutes = to_stop.arrival_time.hour * 60 + to_stop.arrival_time.minute
        
        # Handle next day journeys
        if to_minutes >= from_minutes:
            diff = to_minutes - from_minutes
        else:
            diff = (to_minutes + 1440) - from_minutes  # Add 24 hours (24*60=1440)
        
        hours = diff // 60
        minutes = diff % 60
        
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "< 1m"
    except Exception as e:
        return "N/A"