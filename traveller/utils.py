# traveller/utils.py
from decimal import Decimal
from typing import List, Tuple, Dict
from .models import SeatSegment


def get_available_segments(schedule_id: int, seat_number: int, total_stops: int) -> List[Tuple[int, int]]:
    """
    Get all available segments for a seat.
    Simple logic: Find gaps between booked segments.
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


def get_available_segments_from_boarding(schedule_id: int, seat_number: int, boarding_order: int, total_stops: int) -> List[Tuple[int, int]]:
    """
    Get available segments that start exactly at the boarding point.
    """
    all_available = get_available_segments(schedule_id, seat_number, total_stops)
    valid_segments = [(f, t) for f, t in all_available if f == boarding_order]
    return valid_segments


def is_segment_available(schedule_id: int, seat_number: int, from_order: int, to_order: int) -> bool:
    """Check if a specific segment is available for booking"""
    # Check for any overlapping booking
    overlapping = SeatSegment.objects.filter(
        schedule_id=schedule_id,
        seat_number=seat_number,
        is_active=True,
        from_stop__order__lt=to_order,
        to_stop__order__gt=from_order
    ).exists()
    
    return not overlapping


def calculate_segment_fare(base_fare: Decimal, from_order: int, to_order: int, price_per_stop: Decimal) -> Decimal:
    """Calculate fare for a segment"""
    stops = to_order - from_order
    return base_fare + (stops * price_per_stop)


# Alias for compatibility
calculate_segment_fare = calculate_segment_fare
calculate_fare = calculate_segment_fare


def get_all_available_segments_for_seat(schedule_id: int, seat_number: int, total_stops: int) -> Dict:
    """Get comprehensive availability for a seat"""
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