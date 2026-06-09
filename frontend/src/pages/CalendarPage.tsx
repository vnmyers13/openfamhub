import { useState } from 'react'
import { Calendar, momentLocalizer } from 'react-big-calendar'
import moment from 'moment'
import 'react-big-calendar/lib/css/react-big-calendar.css'

const localizer = momentLocalizer(moment)

export default function CalendarPage() {
  const [events, setEvents] = useState([])

  return (
    <div className="h-[calc(100vh-4rem)]">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Family Calendar</h2>
      </div>
      <div className="h-full bg-[#16213e] rounded-xl p-4">
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: '100%' }}
          views={['month', 'week', 'day']}
          defaultView="month"
          messages={{
            next: 'Next',
            previous: 'Prev',
            today: 'Today',
            month: 'Month',
            week: 'Week',
            day: 'Day',
          }}
        />
      </div>
    </div>
  )
}
