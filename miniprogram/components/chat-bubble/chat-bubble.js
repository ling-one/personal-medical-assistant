Component({
  properties: {
    role: { type: String, value: 'user' },
    content: { type: String, value: '' },
    timestamp: { type: Number, value: 0 },
    showCursor: { type: Boolean, value: false }
  },

  data: {
    timeStr: ''
  },

  observers: {
    'timestamp': function (ts) {
      if (ts) {
        const d = new Date(ts)
        const h = String(d.getHours()).padStart(2, '0')
        const m = String(d.getMinutes()).padStart(2, '0')
        this.setData({ timeStr: `${h}:${m}` })
      }
    }
  }
})
