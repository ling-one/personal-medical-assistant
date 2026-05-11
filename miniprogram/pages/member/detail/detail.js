const { memberApi } = require('../../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../../utils/util')
const app = getApp()

Page({
  data: {
    member: {}
  },

  onLoad(options) {
    this.memberId = options.memberId
    this.loadMember()
  },

  async loadMember() {
    if (!this.memberId) return

    try {
      showLoading()
      const member = await memberApi.getDetail(this.memberId)
      this.setData({ member })
      wx.setNavigationBarTitle({ title: member.name })
      hideLoading()
    } catch (err) {
      hideLoading()
      showToast('加载失败: ' + (err.message || ''))
    }
  },

  goEdit() {
    wx.navigateTo({
      url: `/pages/member/edit/edit?memberId=${this.memberId}`
    })
  },

  goUploadReport() {
    wx.navigateTo({
      url: `/pages/report/detail/detail?memberId=${this.memberId}`
    })
  },

  goChat() {
    wx.switchTab({
      url: '/pages/chat/chat'
    })
    // 延迟设置，让 chat 页面有时间加载
    setTimeout(() => {
      const pages = getCurrentPages()
      const chatPage = pages.find(p => p.route === 'pages/chat/chat')
      if (chatPage) {
        chatPage.setData({ selectedMember: this.data.member })
      }
    }, 500)
  },

  goReportList() {
    wx.navigateTo({
      url: `/pages/report/list/list?memberId=${this.memberId}`
    })
  },

  deleteMember() {
    wx.showModal({
      title: '确认删除',
      content: '确定要删除该成员及其所有数据吗？',
      success: async (res) => {
        if (res.confirm) {
          try {
            showLoading('删除中...')
            await memberApi.delete(this.memberId)
            hideLoading()
            showToast('已删除')
            wx.navigateBack()
          } catch (err) {
            hideLoading()
            showToast('删除失败: ' + (err.message || ''))
          }
        }
      }
    })
  }
})
