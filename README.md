# Airline DB

This is a course project for CSCI-SHU 213 Databases.

## Bonus functionalities

### Search enhancements

- [x] Airport and city in one single search box (Search airport code first, and fallback to city if not matched)
  - [x] Only allow free input of airports and cities for airline staff with admin permission when solely creating airports and cities
  - [x] For other cases, provide a **searchable** drop-down menu
- [x] Blur search on cities: case-insensitive, match by containing instead of equal

## TODO I

Customer dashboard:
- [x] In purchased flights panel, also enable blur search city search in `origin airport` field and `destination airport` field.
- [x] Add labels to the date range input boxes to indicate start date and end date
- [x] For the review spending, set the default view as a custom view with default arguments. i.e., merge the two views.

Booking Agents:
- [x] For comission and number of sold tickets, display both in past 30 days and over all of the time

Airline Staff:
- [x] Display analytics: tickets sold per month by year, and set the default year to display as the current year.
- [x] Display delay vs on-time statistics grouping by year instead of displaying last year's
- [x] Rank top destinations on number of tickets sold to that destination, isntead of flights to that destination
- [x] For all form fields where flight numbers are inputted, make the former airline field not editable, since the airline staff can only edit flights in their own airline. (The sql statement was correct, but the displayed form entry was editable)

## TODO II

Airline Staff dashboard:
- [x] Replace the add airplane and add airport box with a searchable list. When the search term is not matched, give the option to add an airplane or airport. List ten for each by default.
  - [x] If fail to add an airport or airplane, instead of only reporting error "fail to add”, report if it is because the entry already exists.
- [x] Arrange the airline staff analytics panel more clearly. Make it more readable. Indicate which components are only affected by the year filter, which are affected by both year and month filter, and which are not affected by any filter.

Register:
- [x] Change the airline field of the register form of airline staff to be a searchable dropdown menu.
- [x] If the booking agent ID is actually useless, remove that field.