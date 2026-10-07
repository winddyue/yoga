// 预约状态 -> 展示文案。约课页与「我的预约/签到记录」共用一份，避免两处维护不一致。
const STATUS_TEXT = {
  booked: '已预约',
  waitlist: '候补中',
  checked_in: '已签到',
  no_show: '爽约',
  cancelled: '已取消',
};

// 状态分组：「我的预约」看进行中的，「签到记录」看已完结的
const BOOKING_STATUSES = ['booked', 'waitlist', 'cancelled'];
const CHECKIN_STATUSES = ['checked_in', 'no_show'];

module.exports = { STATUS_TEXT, BOOKING_STATUSES, CHECKIN_STATUSES };
