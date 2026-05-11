const { groupApi } = require('../../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../../utils/util')
const app = getApp()

Page({
  data: {
    groupNumber: ''
  },

  onInput(e) {
    this.setData({ groupNumber: e.detail.value })
  },

  async joinGroup() {
    const number = this.data.groupNumber.trim()
    if (number.length !== 9) {
      showToast('请输入完整的9位组号')
      return
    }

    const user_id = app.globalData.user_id
    if (!user_id) {
      showToast('请先初始化')
      return
    }

    try {
      showLoading('加入中...')
      const group = await groupApi.join(number, user_id)

      app.globalData.group_id = group.group_id
      wx.setStorageSync('group_id', group.group_id)

      hideLoading()
      showToast('加入成功')

      wx.switchTab({ url: '/pages/index/index' })
    } catch (err) {
      hideLoading()
      showToast('加入失败: ' + (err.message || ''))
    }
  }
})
