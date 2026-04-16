from django.core.management.base import BaseCommand
from traveller.models import Booking, SeatSegment

class Command(BaseCommand):
    help = 'Create missing SeatSegment records for existing bookings'

    def handle(self, *args, **options):
        # Find bookings without seat segments
        bookings = Booking.objects.filter(segments__isnull=True)
        
        self.stdout.write(f"Found {bookings.count()} bookings without segments")
        
        created_count = 0
        for booking in bookings:
            if booking.from_stop and booking.to_stop:
                segment, created = SeatSegment.objects.get_or_create(
                    booking=booking,
                    schedule=booking.schedule,
                    seat_number=booking.seat_number,
                    from_stop=booking.from_stop,
                    to_stop=booking.to_stop,
                    defaults={
                        'segment_fare': booking.total_fare,
                        'is_active': True
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f"Created segment for booking {booking.id} (Seat {booking.seat_number})")
        
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} seat segments"))