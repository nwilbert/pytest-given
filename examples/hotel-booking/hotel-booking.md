# pytest-given — Hotel Booking Example

## ✓ A search offers only the available rooms
`examples/hotel-booking/test_hotel_booking.py:197::test_pick_suite`

- **given** our organizer «Carol»
- **given** the «Deluxe Suite» is listed as available
- **when** «Carol» searches for a «Room»
- **then** only the «Deluxe Suite» is offered
- **when** «Carol» selects the «Deluxe Suite»
- **then** the «Deluxe Suite» is selected for the group

## ✓ A paid booking is confirmed to every guest
`examples/hotel-booking/test_hotel_booking.py:219::test_complete_booking`

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has selected the «Deluxe Suite»
- **when** «Carol» adds «Alice» and «Bob» to the «Booking»
- **when** «Carol» submits the «Payment» for the «Booking»
- **then** the «Booking System» «confirms» the «Booking»
- **then** the «Booking System» sends the «Confirmation» to «Alice» and «Bob»
- **when** «Alice» and «Bob» check in to the «Deluxe Suite»
- **then** both guests are checked in

## ✗ A declined payment leaves the booking pending · 4 cases
`examples/hotel-booking/test_hotel_booking.py:258::test_payment_declined` · error-handling, ticket/HB-17

- **given** our organizer «Carol»
- **given** our guest «Alice»
- **given** our guest «Bob»
- **given** «Carol» has added «Alice» and «Bob» to the «Booking»
- **when** «Carol» submits the «Payment» by {payment_method} for the «Booking»
- **then** the «Booking System» «declines» the «Payment» because of {decline_reason}
- **then** the «Booking» stays pending and no «Confirmation» is sent to «Alice» or «Bob»

| payment_method | decline_reason | |
|---|---|---|
| credit card | insufficient funds | ✓ |
| debit card | expired card | ✓ |
| bank transfer | fraud check failed | ✓ |
| gift card | partial balance | ✗ |

- **gift card, partial balance** — failed:
  > assert 'unsupported payment method' == 'partial balance'
  > test_hotel_booking.py:293 in test_payment_declined

## ✓ Cancelling a paid booking refunds it and notifies the guest
`examples/hotel-booking/test_hotel_booking.py:312::test_cancel_booking`

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» she paid for
- **when** «Alice» «cancels» the «Booking»
- **then** the «Booking System» «refunds» the «Payment» for the «Booking»
- **then** the «Booking System» sends a «Confirmation» to «Alice»

## ⊗ Rebooking restores a cancelled booking · expected failure
`examples/hotel-booking/test_hotel_booking.py:331::test_rebook_cancelled_booking` — expected to fail: rebooking is not implemented yet

- **given** our guest «Alice»
- **given** «Alice» has cancelled her stay
- **when** «Alice» «rebooks» the «Booking»

> rebooking a cancelled booking is not supported yet
> test_hotel_booking.py:328 in rebook_cancelled_booking

## ✓ A booking can be cancelled only before its guest checks in
`examples/hotel-booking/test_hotel_booking.py:351::test_check_in_then_cancel` · error-handling

- **given** our guest «Alice»
- **given** «Alice» has a confirmed «Booking» now and one next month
- **when** «Alice» checks in to the «Deluxe Suite»
- **then** her current stay is checked in
- **when** «Alice» «cancels» her later «Booking»
- **then** the later booking is cancelled
- **when** she tries to cancel the stay she has checked in to
- **then** the cancellation is refused
