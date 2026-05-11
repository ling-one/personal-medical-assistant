const { showToast } = require('../../utils/util')
const app = getApp()

Page({
  data: {
    userId: '',
    userIdShort: ''
  },

  onShow() {
    const user_id = app.globalData.user_id || wx.getStorageSync('user_id') || ''
    this.setData({
      userId: user_id,
      userIdShort: user_id ? user_id.slice(0, 8) + '...' : '未登录'
    })
  },

  goReportList() {
    wx.navigateTo({ url: '/pages/report/list/list' })
  },

  goMemberList() {
    wx.switchTab({ url: '/pages/index/index' })
  },

  goGroupManage() {
    wx.showActionSheet({
      itemList: ['查看组号', '创建新家庭组', '加入家庭组'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.showGroupNumber()
        } else if (res.tapIndex === 1) {
          wx.navigateTo({ url: '/pages/group/create/create' })
        } else {
          wx.navigateTo({ url: '/pages/group/join/join' })
        }
      }
    })
  },

  async showGroupNumber() {
    const { groupApi } = require('../../utils/api')
    const groupId = app.globalData.group_id
    if (!groupId) {
      showToast('尚未加入任何家庭组')
      return
    }
    try {
      const group = await groupApi.getDetail(groupId)
      wx.showModal({
        title: '家庭组信息',
        content: `组名：${group.group_name}\n组号：${group.group_number}`,
        showCancel: false
      })
    } catch (err) {
      showToast('获取组信息失败')
    }
  },

  resetApp() {
    wx.showModal({
      title: '确认重置',
      content: '重置将清除所有本地数据，应用将重新初始化。确定要重置吗？',
      success: (res) => {
        if (res.confirm) {
          wx.clearStorageSync()
          app.globalData.user_id = ''
          app.globalData.group_id = ''
          showToast('已重置')
          wx.switchTab({ url: '/pages/index/index' })
        }
      }
    })
  }
})
