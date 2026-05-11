const { memberApi } = require('../../utils/api')
const { showToast } = require('../../utils/util')
const app = getApp()

Page({
  data: {
    members: [],
    selectedMember: null,
    messages: [],
    inputValue: '',
    loading: false,
    historyLoading: false,
    conversationId: '',
    scrollToId: '',
    streamingContent: '',
    showStreamingCursor: false,
    suggestions: [
      '最近有点头疼，怎么办？',
      '如何预防感冒？',
      '体检报告怎么看？',
      '高血压日常注意事项'
    ],
    safeBottom: false
  },

  onLoad() {
    this.loadMembers()
  },

  onShow() {
    if (!this.data.members.length) {
      this.loadMembers()
    }
  },

  async loadMembers() {
    const groupId = app.globalData.group_id
    if (!groupId) return
    try {
      const members = await memberApi.getList(groupId)
      this.setData({ members: members || [] })
    } catch (err) {
      // 静默失败
    }
  },

  onMemberSelect(e) {
    const member = e.detail
    if (this.data.selectedMember?.member_id === member.member_id) {
      this.setData({ selectedMember: null, messages: [], conversationId: '' })
    } else {
      this._switchToConversation(member)
    }
  },

  async _switchToConversation(member) {
    this.setData({
      selectedMember: member,
      messages: [],
      conversationId: '',
      historyLoading: true
    })

    const user_id = app.globalData.user_id
    if (!user_id) {
      this.setData({ historyLoading: false })
      return
    }

    const { chatApi } = require('../../utils/api')
    try {
      const conversations = await chatApi.listConversations(user_id)
      let convId = ''
      if (conversations.conversations) {
        const match = conversations.conversations.find(
          c => c.member_id === member.member_id
        )
        if (match) {
          convId = match.conversation_id
        }
      }

      if (convId) {
        this.setData({ conversationId: convId })
        const res = await chatApi.getMessages(convId)
        if (res.messages && res.messages.length > 0) {
          const msgs = res.messages.map(m => ({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp ? m.timestamp * 1000 : Date.now()
          }))
          this.setData({ messages: msgs })
          setTimeout(() => this.scrollToBottom(), 100)
        }
      }
    } catch (err) {
      console.error('加载历史失败:', err)
    } finally {
      this.setData({ historyLoading: false })
    }
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value })
  },

  sendSuggestion(e) {
    const text = e.currentTarget.dataset.text
    this.setData({ inputValue: text })
    this.sendMessage()
  },

  sendMessage() {
    const content = this.data.inputValue.trim()
    if (!content || this.data.loading) return

    const user_id = app.globalData.user_id
    if (!user_id) {
      showToast('请先初始化')
      return
    }

    // 添加用户消息
    const userMsg = { role: 'user', content, timestamp: Date.now() }
    this.setData({
      messages: [...this.data.messages, userMsg],
      inputValue: '',
      loading: true,
      showStreamingCursor: false
    })
    setTimeout(() => this.scrollToBottom(), 100)

    // 添加空 AI 占位消息
    const aiPlaceholder = { role: 'assistant', content: '', timestamp: Date.now() }
    this.setData({
      messages: [...this.data.messages, aiPlaceholder]
    })

    // 发起 WebSocket 流式连接
    this._connectStream(content, user_id)
  },

  _connectStream(content, user_id) {
    const baseUrl = app.globalData.baseUrl
    const wsUrl = baseUrl.replace(/^http/, 'ws') + '/chat/ws'

    const socketTask = wx.connectSocket({ url: wsUrl })

    socketTask.onOpen(() => {
      socketTask.send({
        data: JSON.stringify({
          message: content,
          user_id,
          conversation_id: this.data.conversationId || '',
          member_id: this.data.selectedMember?.member_id || ''
        })
      })
    })

    socketTask.onMessage((res) => {
      try {
        const data = JSON.parse(res.data)

        if (data.type === 'conversation_id') {
          // 保存服务端分配的 conversationId
          this.setData({ conversationId: data.content })
        } else if (data.type === 'status') {
          // 处理中
        } else if (data.type === 'token') {
          const msgs = this.data.messages
          const lastIdx = msgs.length - 1
          const newContent = (msgs[lastIdx].content || '') + data.content
          // 微信小程序必须用路径式 setData 才能触发渲染
          this.setData({
            [`messages[${lastIdx}].content`]: newContent,
            showStreamingCursor: true
          })
          // 首 token 到达时滚动到底部
          if (msgs[lastIdx].content === '') {
            setTimeout(() => this.scrollToBottom(), 50)
          }
        } else if (data.type === 'done') {
          this.setData({
            loading: false,
            showStreamingCursor: false
          })
          socketTask.close()
          setTimeout(() => this.scrollToBottom(), 100)
        } else if (data.type === 'error') {
          showToast('错误: ' + data.content)
          this.setData({ loading: false, showStreamingCursor: false })
          socketTask.close()
        }
      } catch (err) {
        console.error('WS 解析失败:', err)
      }
    })

    socketTask.onError(() => {
      showToast('连接失败，切换为非流式模式')
      this._fallbackSend(content, user_id)
    })

    socketTask.onClose(() => {
      if (this.data.loading) {
        this.setData({ loading: false, showStreamingCursor: false })
      }
    })
  },

  async _fallbackSend(content, user_id) {
    // 非流式回退（WebSocket 连接失败时使用）
    const { chatApi } = require('../../utils/api')
    try {
      const res = await chatApi.sendMessage({
        message: content,
        user_id,
        conversation_id: this.data.conversationId || undefined,
        member_id: this.data.selectedMember?.member_id || undefined
      })
      this.setData({ conversationId: res.conversation_id })
      const msgs = this.data.messages
      const lastIdx = msgs.length - 1
      this.setData({
        [`messages[${lastIdx}].content`]: res.message,
        loading: false
      })
      setTimeout(() => this.scrollToBottom(), 100)
    } catch (err) {
      const msgs = this.data.messages
      const lastIdx = msgs.length - 1
      this.setData({
        [`messages[${lastIdx}].content`]: '抱歉，我遇到了问题：' + (err.message || '请稍后重试'),
        loading: false
      })
    }
  },

  scrollToBottom() {
    const msgs = this.data.messages
    if (msgs.length > 0) {
      this.setData({ scrollToId: `msg-${msgs.length - 1}` })
    }
  },

  preventTouch() {
    // 防止聊天区域触摸穿透
  }
})
