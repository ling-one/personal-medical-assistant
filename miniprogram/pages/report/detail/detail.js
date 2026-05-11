const { reportApi, chatApi } = require('../../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../../utils/util')
const app = getApp()

Page({
  data: {
    reportId: '',
    memberId: '',
    ocrText: '',
    analysis: null,
    analysisRaw: null
  },

  onLoad(options) {
    if (options.reportId) {
      this.setData({ reportId: options.reportId })
    }
    if (options.memberId) {
      this.setData({ memberId: options.memberId })
      wx.setStorageSync('report_member_id', options.memberId)
    }
  },

  uploadReport() {
    const memberId = this.data.memberId || wx.getStorageSync('report_member_id')
    if (!memberId) {
      showToast('请先选择成员')
      return
    }

    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success: (res) => {
        const sourceType = res.tapIndex === 0 ? 'camera' : 'album'
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType: [sourceType],
          success: (mediaRes) => {
            this.doAnalyze(mediaRes.tempFiles[0].tempFilePath, memberId)
          }
        })
      }
    })
  },

  async doAnalyze(filePath, memberId) {
    try {
      showLoading('AI 分析中...')
      const result = await reportApi.analyze(filePath, memberId)

      this.setData({
        ocrText: result.ocr_text,
        analysis: result.analysis || {},
        analysisRaw: result
      })

      wx.setNavigationBarTitle({ title: '分析结果' })
      hideLoading()
      showToast('分析完成')
    } catch (err) {
      hideLoading()
      showToast('分析失败: ' + (err.message || ''))
    }
  },

  goChat() {
    wx.switchTab({ url: '/pages/chat/chat' })
  }
})
