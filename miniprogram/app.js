App({
  globalData: {
    user_id: '',
    group_id: '',
    baseUrl: 'http://localhost:8000/api'
  },

  onLaunch() {
    const user_id = wx.getStorageSync('user_id')
    const group_id = wx.getStorageSync('group_id')
    const server_url = wx.getStorageSync('server_url')
    if (user_id) {
      this.globalData.user_id = user_id
      this.globalData.group_id = group_id || ''
    }
    if (server_url) {
      this.globalData.baseUrl = server_url
    }
  }
})
