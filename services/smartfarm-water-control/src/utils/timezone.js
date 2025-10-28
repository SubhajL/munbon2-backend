/**
 * Timezone conversion utilities for MSSQL valve command timestamps
 */

/**
 * Get timezone offset in minutes for a given timezone at a specific date
 * @param {string} timezone - IANA timezone name (e.g. 'Asia/Bangkok')
 * @param {Date} referenceDate - Date to calculate offset for
 * @returns {number} Offset in minutes from UTC (positive = ahead of UTC)
 */
function getTimezoneOffsetMinutes(timezone, referenceDate) {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });

    const parts = formatter.formatToParts(referenceDate);
    const localComponents = {};
    parts.forEach((part) => {
      if (part.type !== 'literal') {
        localComponents[part.type] = parseInt(part.value, 10);
      }
    });

    const localDate = new Date(
      Date.UTC(
        localComponents.year,
        localComponents.month - 1,
        localComponents.day,
        localComponents.hour,
        localComponents.minute,
        localComponents.second
      )
    );

    const offsetMs = localDate.getTime() - referenceDate.getTime();
    return Math.round(offsetMs / (1000 * 60));
  } catch (error) {
    return 0;
  }
}

/**
 * Convert UTC Date to local time in specified timezone
 * @param {Date} utcDate - UTC Date object
 * @param {string} timezone - IANA timezone name (e.g. 'Asia/Bangkok')
 * @returns {Date} New Date object with UTC components representing local time
 */
function convertUTCToLocalTime(utcDate, timezone) {
  const offsetMinutes = getTimezoneOffsetMinutes(timezone, utcDate);
  const localTimeMs = utcDate.getTime() + offsetMinutes * 60 * 1000;
  return new Date(localTimeMs);
}

/**
 * Format Date object for MSSQL datetime column
 * @param {Date} date - Date object (should be in UTC representation of local time)
 * @returns {string} Formatted string 'YYYY-MM-DD HH:MM:SS'
 */
function formatDateForMSSQL(date) {
  const pad = (num) => String(num).padStart(2, '0');
  return (
    `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ` +
    `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`
  );
}

module.exports = {
  getTimezoneOffsetMinutes,
  convertUTCToLocalTime,
  formatDateForMSSQL
};
