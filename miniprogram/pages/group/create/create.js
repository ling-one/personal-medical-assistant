const { groupApi } = require('../../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../../utils/util')
const app = getApp()

Page({
  data: {
    groupName: ''
  },

  onInput(e) {
    this.setData({ groupName: e.detail.value })
  },

  async createGroup() {
    const name = this.data.groupName.trim()
    if (!name) {
      showToast('请输入家庭组名称')
      return
    }

    const user_id = app.globalData.user_id
    if (!user_id) {
      showToast('请先初始化')
      return
    }

    try {
      showLoading('创建中...')
      const group = await groupApi.create(name, user_id)

      app.globalData.group_id = group.group_id
      wx.setStorageSync('group_id', group.group_id)

      hideLoading()
      showToast('创建成功')

      // 显示组号
      wx.showModal({
        title: '家庭组已创建',
        content: `组号：${group.group_number}\n\n家人可通过此组号加入您的家庭组。\n请妥善保管！`,
        showCancel: false,
        success: () => {
          wx.switchTab({ url: '/pages/index/index' })
        }
      })
    } catch (err) {
      hideLoading()
      showToast('创建失败: ' + (err.message || ''))
    }
  }
})
