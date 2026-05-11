const { groupApi, memberApi, userApi } = require('../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../utils/util')
const app = getApp()

Page({
  data: {
    groupLoaded: false,
    groupName: '',
    groupId: '',
    members: []
  },

  onShow() {
    this.init()
  },

  async init() {
    // 检查是否有用户ID
    const user_id = app.globalData.user_id
    const group_id = app.globalData.group_id

    if (!user_id) {
      await this.createUser()
    }

    if (group_id) {
      this.loadGroupData(group_id)
    } else {
      // 查找用户已有的家庭组
      this.loadUserGroups()
    }
  },

  async createUser() {
    try {
      showLoading('初始化...')
      const res = await userApi.create()
      app.globalData.user_id = res.user_id
      wx.setStorageSync('user_id', res.user_id)
      hideLoading()
    } catch (err) {
      hideLoading()
      showToast('初始化失败: ' + (err.message || '未知错误'))
    }
  },

  async loadUserGroups() {
    const user_id = app.globalData.user_id
    if (!user_id) return

    try {
      const groups = await groupApi.getUserGroups(user_id)
      if (groups && groups.length > 0) {
        const group = groups[0]
        app.globalData.group_id = group.group_id
        wx.setStorageSync('group_id', group.group_id)
        this.loadGroupData(group.group_id)
      } else {
        this.setData({ groupLoaded: false })
      }
    } catch (err) {
      this.setData({ groupLoaded: false })
    }
  },

  async loadGroupData(groupId) {
    try {
      showLoading('加载中...')
      const [group, members] = await Promise.all([
        groupApi.getDetail(groupId),
        memberApi.getList(groupId)
      ])
      this.setData({
        groupLoaded: true,
        groupName: group.group_name,
        groupId: group.group_id,
        members: members || []
      })
      hideLoading()
    } catch (err) {
      hideLoading()
      showToast('加载失败: ' + (err.message || ''))
    }
  },

  goCreateGroup() {
    wx.navigateTo({ url: '/pages/group/create/create' })
  },

  goJoinGroup() {
    wx.navigateTo({ url: '/pages/group/join/join' })
  },

  goAddMember() {
    const groupId = this.data.groupId
    if (!groupId) {
      showToast('请先创建家庭组')
      return
    }
    wx.navigateTo({ url: `/pages/member/edit/edit?groupId=${groupId}` })
  },

  goUploadReport() {
    const members = this.data.members
    if (members.length === 0) {
      showToast('请先添加家庭成员')
      return
    }
    // 跳转到报告页
    wx.navigateTo({ url: '/pages/report/list/list' })
  },

  goMemberDetail(e) {
    const memberId = e.currentTarget.dataset.memberId
    wx.navigateTo({ url: `/pages/member/detail/detail?memberId=${memberId}` })
  }
})
