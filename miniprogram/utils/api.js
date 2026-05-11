const app = getApp()

// 是否启用 mock（调试时可用，默认不启用）
const USE_MOCK = false

// ==================== 基础请求封装 ====================

function request(method, path, data, isForm = false) {
  const baseUrl = app.globalData.baseUrl
  const url = `${baseUrl}${path}`

  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method,
      data,
      header: isForm
        ? { 'Content-Type': 'multipart/form-data' }
        : { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject({ code: res.statusCode, message: res.data?.detail || '请求失败' })
        }
      },
      fail: (err) => {
        reject({ code: -1, message: '网络异常，请检查服务器连接' })
      }
    })
  })
}

function get(path, data) {
  return request('GET', path, data)
}

function post(path, data) {
  return request('POST', path, data)
}

function put(path, data) {
  return request('PUT', path, data)
}

function del(path) {
  return request('DELETE', path)
}

// ==================== 文件上传 ====================

function uploadFile(path, filePath, formData) {
  const baseUrl = app.globalData.baseUrl
  const url = `${baseUrl}${path}`

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url,
      filePath,
      name: 'file',
      formData,
      success: (res) => {
        try {
          const data = JSON.parse(res.data)
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(data)
          } else {
            reject({ code: res.statusCode, message: data?.detail || '上传失败' })
          }
        } catch (e) {
          reject({ code: -1, message: '解析响应失败' })
        }
      },
      fail: () => {
        reject({ code: -1, message: '上传失败，请重试' })
      }
    })
  })
}

// ==================== 用户 API ====================

const userApi = {
  create(userId) {
    return post('/user/create', userId ? { user_id: userId } : {})
  },
  getInfo(userId) {
    return get(`/user/${userId}`)
  }
}

// ==================== 家庭组 API ====================

const groupApi = {
  getUserGroups(userId) {
    return get(`/group/user/${userId}`)
  },
  create(groupName, userId) {
    return post('/group/create', { group_name: groupName, user_id: userId })
  },
  join(groupNumber, userId) {
    return post(`/group/join/${groupNumber}`, null, { user_id: userId })
  },
  getDetail(groupId) {
    return get(`/group/${groupId}`)
  },
  delete(groupId) {
    return del(`/group/${groupId}`)
  }
}

// ==================== 成员 API ====================

const memberApi = {
  create(groupId, data) {
    return post(`/member/group/${groupId}`, data)
  },
  getList(groupId) {
    return get(`/member/group/${groupId}`)
  },
  getDetail(memberId) {
    return get(`/member/${memberId}`)
  },
  update(memberId, data) {
    return put(`/member/${memberId}`, data)
  },
  delete(memberId) {
    return del(`/member/${memberId}`)
  },
  updateMedicalHistory(memberId, data) {
    return put(`/member/${memberId}/medical-history`, data)
  },
  updateVitalSigns(memberId, data) {
    return put(`/member/${memberId}/vital-signs`, data)
  },
  getSummary(memberId) {
    return get(`/member/${memberId}/summary`)
  }
}

// ==================== 对话 API ====================

const chatApi = {
  sendMessage(data) {
    return post('/chat/message', data)
  },
  getHistory(conversationId) {
    return get(`/chat/history/${conversationId}`)
  },
  submitFeedback(data) {
    return post('/chat/feedback', data)
  },
  listConversations(userId) {
    return get('/chat/conversations', { user_id: userId })
  },
  getMessages(conversationId) {
    return get(`/chat/messages/${conversationId}`)
  },
  clearConversation(userId, memberId) {
    return request('DELETE', '/chat/conversations', { user_id: userId, member_id: memberId || '' })
  }
}

// ==================== 报告 API ====================

const reportApi = {
  upload(filePath, memberId) {
    return uploadFile('/report/upload', filePath, { member_id: memberId })
  },
  analyze(filePath, memberId) {
    return uploadFile('/report/analyze', filePath, { member_id: memberId })
  }
}

// ==================== 知识库 API ====================

const knowledgeApi = {
  search(query, topK = 5, category) {
    const params = { query, top_k: topK }
    if (category) params.category = category
    return get('/knowledge/search', params)
  },
  getCategories() {
    return get('/knowledge/categories')
  }
}

module.exports = {
  get, post, put, del, uploadFile,
  userApi,
  groupApi,
  memberApi,
  chatApi,
  reportApi,
  knowledgeApi
}
