const { memberApi, reportApi } = require('../../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../../utils/util')
const app = getApp()

Page({
  data: {
    members: [],
    memberNames: [],
    selectedIndex: -1,
    selectedMember: null,
    reports: []
  },

  onLoad() {
    this.loadMembers()
  },

  async loadMembers() {
    const groupId = app.globalData.group_id
    if (!groupId) return

    try {
      const members = await memberApi.getList(groupId)
      const memberNames = members.map(m => `${m.name}（${m.relationship}）`)
      this.setData({ members, memberNames })
    } catch (err) {
      showToast('加载成员失败')
    }
  },

  onMemberChange(e) {
    const idx = e.detail.value
    const member = this.data.members[idx]
    this.setData({
      selectedIndex: idx,
      selectedMember: member
    })
    this.loadReports(member.member_id)
  },

  loadReports(memberId) {
    // 注意：后端暂无报告列表接口，这里通过本地缓存读取
    // 首次使用时显示空列表，上传后会通过缓存记录
    const key = `reports_${memberId}`
    try {
      const cached = wx.getStorageSync(key) || []
      this.setData({ reports: cached.map(r => ({
        ...r,
        created_at_formatted: r.created_at
          ? new Date(r.created_at).toLocaleDateString('zh-CN')
          : '--'
      })) })
    } catch (e) {
      this.setData({ reports: [] })
    }
  },

  uploadReport() {
    const member = this.data.selectedMember
    if (!member) return

    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.takePhoto(member.member_id)
        } else {
          this.chooseImage(member.member_id)
        }
      }
    })
  },

  takePhoto(memberId) {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: (res) => {
        this.doUpload(res.tempFiles[0].tempFilePath, memberId)
      }
    })
  },

  chooseImage(memberId) {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album'],
      success: (res) => {
        this.doUpload(res.tempFiles[0].tempFilePath, memberId)
      }
    })
  },

  async doUpload(filePath, memberId) {
    try {
      showLoading('正在分析报告...')
      const result = await reportApi.analyze(filePath, memberId)

      // 缓存报告记录
      const key = `reports_${memberId}`
      const cached = wx.getStorageSync(key) || []
      cached.unshift({
        report_id: result.report_id,
        filename: result.report_id ? `报告_${cached.length + 1}` : '上传文件',
        analysis: result.analysis?.summary || result.ocr_text?.slice(0, 100),
        created_at: new Date().toISOString()
      })
      wx.setStorageSync(key, cached)

      hideLoading()
      showToast('分析完成')

      // 刷新列表
      this.loadReports(memberId)
    } catch (err) {
      hideLoading()
      showToast('上传失败: ' + (err.message || ''))
    }
  },

  viewReport(e) {
    const report = e.currentTarget.dataset.report
    const member = this.data.selectedMember
    wx.navigateTo({
      url: `/pages/report/detail/detail?reportId=${report.report_id}&memberId=${member.member_id}`
    })
  }
})
