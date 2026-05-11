const { memberApi } = require('../../../utils/api')
const { showToast, showLoading, hideLoading } = require('../../../utils/util')
const app = getApp()

function getTodayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

Page({
  data: {
    isEdit: false,
    memberId: '',
    groupId: '',
    form: {
      name: '',
      relationship: '',
      gender: '男',
      birthDate: '',
      height: '',
      weight: ''
    },
    relationList: ['本人', '配偶', '儿子', '女儿', '父亲', '母亲', '兄弟', '姐妹', '其他'],
    relationIndex: -1,
    today: getTodayStr()
  },

  onLoad(options) {
    this.setData({ today: getTodayStr() })

    if (options.memberId) {
      // 编辑模式
      this.setData({
        isEdit: true,
        memberId: options.memberId
      })
      this.loadMemberData()
    } else if (options.groupId) {
      this.setData({ groupId: options.groupId })
    } else {
      this.setData({ groupId: app.globalData.group_id })
    }
  },

  async loadMemberData() {
    try {
      showLoading()
      const member = await memberApi.getDetail(this.data.memberId)
      const relationIndex = this.data.relationList.indexOf(member.relationship)
      const birthDate = member.birth_date || ''
      this.setData({
        groupId: member.group_id,
        form: {
          name: member.name || '',
          relationship: member.relationship || '',
          gender: member.gender || '男',
          birthDate: typeof birthDate === 'string' ? birthDate.split('T')[0] : '',
          height: member.height ? String(member.height) : '',
          weight: member.weight ? String(member.weight) : ''
        },
        relationIndex
      })
      hideLoading()
    } catch (err) {
      hideLoading()
      showToast('加载失败')
    }
  },

  onFieldInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({
      [`form.${field}`]: e.detail.value
    })
  },

  onRelationChange(e) {
    const idx = e.detail.value
    this.setData({
      relationIndex: idx,
      'form.relationship': this.data.relationList[idx]
    })
  },

  setGender(e) {
    this.setData({ 'form.gender': e.currentTarget.dataset.value })
  },

  onDateChange(e) {
    this.setData({ 'form.birthDate': e.detail.value })
  },

  async saveMember() {
    const form = this.data.form
    if (!form.name.trim()) {
      showToast('请输入姓名')
      return
    }
    if (!form.relationship) {
      showToast('请选择关系')
      return
    }
    if (!form.birthDate) {
      showToast('请选择出生日期')
      return
    }

    const payload = {
      name: form.name.trim(),
      relationship: form.relationship,
      gender: form.gender,
      birth_date: form.birthDate,
      height: form.height ? parseFloat(form.height) : undefined,
      weight: form.weight ? parseFloat(form.weight) : undefined
    }

    try {
      showLoading(this.data.isEdit ? '保存中...' : '添加中...')

      if (this.data.isEdit) {
        await memberApi.update(this.data.memberId, payload)
        showToast('保存成功')
      } else {
        await memberApi.create(this.data.groupId, payload)
        showToast('添加成功')
      }

      hideLoading()
      wx.navigateBack()
    } catch (err) {
      hideLoading()
      showToast('操作失败: ' + (err.message || ''))
    }
  }
})
