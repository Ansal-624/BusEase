# traveller/utils.py
from decimal import Decimal
from typing import List, Tuple, Dict, Optional
from .models import SeatSegment
from bus_owner.models import RouteStop
import logging

logger = logging.getLogger(__name__)


def is_segment_available(schedule_id: int, seat_number: int, from_order: int, to_order: int) -> bool:
    """
    Check if a specific segment is available for booking.
    
    A segment is available if there is NO overlapping booking.
    Overlap occurs when:
        Existing booking: A to B
        New booking: X to Y
        Overlap exists if: X < B AND Y > A
    
    Args:
        schedule_id: ID of the bus schedule
        seat_number: Seat number to check
        from_order: Boarding stop order (starting point)
        to_order: Destination stop order (ending point)
    
    Returns:
        True if segment is available, False if overlapping booking exists
    """
    try:
        # Check for any overlapping active segments
        overlapping = SeatSegment.objects.filter(
            schedule_id=schedule_id,
            seat_number=seat_number,
            is_active=True,
            from_stop__order__lt=to_order,  # Existing booking starts before new booking ends
            to_stop__order__gt=from_order    # Existing booking ends after new booking starts
        ).exists()
        
        # Log for debugging
        if overlapping:
            # Get the conflicting segment details for logging
            conflict = SeatSegment.objects.filter(
                schedule_id=schedule_id,
                seat_number=seat_number,
                is_active=True,
                from_stop__order__lt=to_order,
                to_stop__order__gt=from_order
            ).select_related('from_stop', 'to_stop').first()
            
            if conflict:
                logger.debug(
                    f"Seat {seat_number} NOT available: Conflict with booking "
                    f"from {conflict.from_stop.stop_name}(order {conflict.from_stop.order}) "
                    f"to {conflict.to_stop.stop_name}(order {conflict.to_stop.order}) "
                    f"vs requested {from_order} to {to_order}"
                )
        else:
            logger.debug(f"Seat {seat_number} available for segment {from_order} to {to_order}")
        
        return not overlapping
        
    except Exception as e:
        logger.error(f"Error checking segment availability: {str(e)}")
        return False  # Return False on error to be safe


def get_overlapping_segment_details(schedule_id: int, seat_number: int, from_order: int, to_order: int) -> Optional[Dict]:
    """
    Get details of the overlapping segment if it exists.
    Returns None if no overlap found.
    """
    try:
        overlapping = SeatSegment.objects.filter(
            schedule_id=schedule_id,
            seat_number=seat_number,
            is_active=True,
            from_stop__order__lt=to_order,
            to_stop__order__gt=from_order
        ).select_related('from_stop', 'to_stop').first()
        
        if overlapping:
            return {
                'from_stop': overlapping.from_stop.stop_name,
                'to_stop': overlapping.to_stop.stop_name,
                'from_order': overlapping.from_stop.order,
                'to_order': overlapping.to_stop.order,
                'booking_id': overlapping.booking.id
            }
        return None
    except Exception as e:
        logger.error(f"Error getting overlapping segment: {str(e)}")
        return None


def get_available_segments(schedule_id: int, seat_number: int, total_stops: int) -> List[Tuple[int, int]]:
    """
    Get all available segments for a seat.
    Returns list of (from_order, to_order) tuples that are available for booking.
    """
    # Get all booked segments for this seat
    booked = SeatSegment.objects.filter(
        schedule_id=schedule_id,
        seat_number=seat_number,
        is_active=True
    ).values_list('from_stop__order', 'to_stop__order')
    
    if not booked:
        # No bookings - entire route available
        return [(1, total_stops)]
    
    # Sort booked segments
    booked_list = sorted([(f, t) for f, t in booked])
    
    # Find available gaps
    available = []
    current = 1
    
    for from_order, to_order in booked_list:
        if current < from_order:
            available.append((current, from_order))
        current = max(current, to_order)
    
    if current < total_stops:
        available.append((current, total_stops))
    
    return available


def get_available_segments_from_boarding(
    schedule_id: int, 
    seat_number: int, 
    boarding_order: int, 
    total_stops: int
) -> List[Tuple[int, int]]:
    """
    Get available segments that start exactly at the boarding point.
    """
    all_available = get_available_segments(schedule_id, seat_number, total_stops)
    valid_segments = [(f, t) for f, t in all_available if f == boarding_order]
    return valid_segments


def get_available_destinations_from_boarding(
    schedule_id: int,
    seat_number: int,
    boarding_order: int,
    total_stops: int
) -> List[int]:
    """
    Get all available destination orders for a specific seat and boarding point.
    """
    valid_segments = get_available_segments_from_boarding(
        schedule_id, seat_number, boarding_order, total_stops
    )
    return [t for f, t in valid_segments]


def get_occupied_segments_for_seat(schedule_id: int, seat_number: int) -> List[Dict]:
    """Get all occupied segments for a seat with details"""
    segments = SeatSegment.objects.filter(
        schedule_id=schedule_id,
        seat_number=seat_number,
        is_active=True
    ).select_related('from_stop', 'to_stop')
    
    occupied = []
    for segment in segments:
        occupied.append({
            'from_order': segment.from_stop.order,
            'to_order': segment.to_stop.order,
            'from_name': segment.from_stop.stop_name,
            'to_name': segment.to_stop.stop_name,
            'from_time': segment.from_stop.arrival_time.strftime("%I:%M %p"),
            'to_time': segment.to_stop.arrival_time.strftime("%I:%M %p"),
        })
    
    return occupied


def get_seat_occupancy_message(occupied_segments: List[Dict], boarding_order: Optional[int] = None) -> Optional[str]:
    """Generate user-friendly message about occupied segments"""
    if not occupied_segments:
        return None
    
    message_lines = ["⚠️ This seat is already booked for:"]
    
    for seg in occupied_segments:
        message_lines.append(f"  • {seg['from_name']} → {seg['to_name']}")
    
    if boarding_order is not None:
        # Check if boarding point is within any occupied segment
        for seg in occupied_segments:
            if seg['from_order'] <= boarding_order < seg['to_order']:
                message_lines.append(f"\n❌ Cannot board at this stop - seat occupied until {seg['to_name']}")
                message_lines.append(f"✓ Available from {seg['to_name']} onwards")
                return "\n".join(message_lines)
    
    return "\n".join(message_lines)


def get_seat_status_text(seat_number: int, schedule_id: int, total_stops: int) -> Dict:
    """Get comprehensive seat status including tooltip text"""
    available_segments = get_available_segments(schedule_id, seat_number, total_stops)
    occupied_segments = get_occupied_segments_for_seat(schedule_id, seat_number)
    
    if not available_segments:
        status = "fully_booked"
        tooltip = "This seat is fully booked for the entire route"
    elif occupied_segments:
        status = "partially_available"
        tooltip_parts = ["Partially available\nBooked for:"]
        for seg in occupied_segments:
            tooltip_parts.append(f"  • {seg['from_name']} → {seg['to_name']}")
        tooltip_parts.append("\nAvailable for remaining segments")
        tooltip = "\n".join(tooltip_parts)
    else:
        status = "available"
        tooltip = "Available for entire route"
    
    return {
        'status': status,
        'tooltip': tooltip,
        'available_segments': available_segments,
        'occupied_segments': occupied_segments
    }


def calculate_segment_fare(base_fare: Decimal, from_order: int, to_order: int, price_per_stop: Decimal) -> Decimal:
    """Calculate fare for a specific segment"""
    stops_travelled = to_order - from_order
    return base_fare + (stops_travelled * price_per_stop)


# Alias for compatibility
calculate_fare = calculate_segment_fare


def get_all_available_segments_for_seat(schedule_id: int, seat_number: int, total_stops: int) -> Dict:
    """
    Get comprehensive availability for a seat including:
    - Available segments
    - Prices for each possible segment
    - Currently booked segments
    """
    booked_segments = SeatSegment.objects.filter(
        schedule_id=schedule_id,
        seat_number=seat_number,
        is_active=True
    ).select_related('from_stop', 'to_stop')
    
    booked_info = []
    for segment in booked_segments:
        booked_info.append({
            'from_stop': segment.from_stop.stop_name,
            'to_stop': segment.to_stop.stop_name,
            'from_order': segment.from_stop.order,
            'to_order': segment.to_stop.order,
            'fare': float(segment.segment_fare)
        })
    
    available_segments = get_available_segments(schedule_id, seat_number, total_stops)
    
    return {
        'seat_number': seat_number,
        'is_fully_available': len(booked_segments) == 0,
        'is_fully_booked': len(available_segments) == 0,
        'booked_segments': booked_info,
        'available_segments': available_segments,
    }