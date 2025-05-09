// 全局配置对象
var config = {};
// 全局分页变量
let allSitesData = [];
let currentPage = 1;
let pageSize = 10;

/**
 * 请求获取所有用户数据
 * @returns {Promise<Array>} 用户数据数组
 */
function fetchUsers() {
  return $.ajax({
    url: '/api/users',
    method: 'GET',
    dataType: 'json'
  }).catch(function(err) {
    console.error('获取用户数据失败:', err);
    return [];
  });
}

/**
 * 请求获取监控配置
 * @returns {Promise<Object>} 监控配置对象
 */
function fetchConfig() {
  return $.ajax({
    url: '/api/config',
    method: 'GET',
    dataType: 'json'
  });
}

/**
 * 请求获取媒体类型配置
 * @returns {Promise<Object>} 媒体类型配置对象
 */
function fetchMediaCodes() {
  return $.ajax({
    url: '/api/config/media_codes',
    method: 'GET',
    dataType: 'json'
  });
}

/**
 * 渲染分页表格
 * @param {Array} data 全部数据
 * @param {number} page 当前页码
 * @param {number} size 每页条数
 */
function renderPagedTable(data, page, size) {
  const $tbody = $('#sites-table-tbody');
  $tbody.empty();
  if (!Array.isArray(data) || data.length === 0) {
    $tbody.append('<tr><td colspan="9" style="text-align:center;">暂无数据</td></tr>');
    updatePagination(0, page, size);
    return;
  }
  // 扁平化所有站点
  let flatList = [];
  data.forEach(user => {
    if (user.sites && Array.isArray(user.sites)) {
      user.sites.forEach(site => {
        flatList.push({ user, site });
      });
    }
  });
  const total = flatList.length;
  const start = (page - 1) * size;
  const end = start + size;
  const pageList = flatList.slice(start, end);
  if (pageList.length === 0) {
    $tbody.append('<tr><td colspan="9" style="text-align:center;">暂无数据</td></tr>');
    updatePagination(total, page, size);
    return;
  }
  pageList.forEach(({ user, site }) => {
    const $tr = $('<tr></tr>');
    $tr.append(`<td>${user.user_id !== undefined ? user.user_id : ''}</td>`);
    const mediaType = config.media_codes && config.media_codes[site.code];
    $tr.append(`<td>${mediaType !== undefined ? mediaType.name : ''}</td>`);
    // 账号类型
    const accountType = config.account_types && config.account_types[site.account_type];
    $tr.append(`<td>${accountType !== undefined ? accountType.name : ''}</td>`);
    // 账号/手机号
    $tr.append(`<td>${site.account !== undefined ? site.account : ''}</td>`);
    // 密码
    $tr.append(`<td>${site.password !== undefined ? site.password : ''}</td>`);
    // 负责人
    $tr.append(`<td>${site.contact !== undefined ? site.contact : ''}</td>`);
    // 描述
    $tr.append(`<td>${site.description !== undefined ? site.description : ''}</td>`);
    // 状态
    $tr.append('<td>--</td>');
    // 操作
    $tr.append('<td>--</td>');
    $tbody.append($tr);
  });
  updatePagination(total, page, size);
}

/**
 * 渲染分页控件
 * @param {number} total 总条数
 * @param {number} page 当前页码
 * @param {number} size 每页条数
 */
function updatePagination(total, page, size) {
  const $pagination = $('#pagination');
  const totalPages = Math.max(1, Math.ceil(total / size));
  let html = '';
  html += `<span>共${total}条 </span>`;
  html += `<button type="button" ${page === 1 ? 'disabled' : ''} class="page-btn" data-page="${page - 1}">上一页</button>`;
  html += `<span> 第${page}/${totalPages}页 </span>`;
  html += `<button type="button" ${page === totalPages ? 'disabled' : ''} class="page-btn" data-page="${page + 1}">下一页</button>`;
  html += `<select id="page-size-select" style="margin-left:8px;">` +
    [10, 20, 50].map(sz => `<option value="${sz}" ${sz === size ? 'selected' : ''}>每页${sz}条</option>`).join('') +
    `</select>`;
  $pagination.html(html);
}

// 分页按钮事件
$(document).on('click', '.page-btn', function () {
  const page = parseInt($(this).data('page'));
  if (!isNaN(page)) {
    currentPage = page;
    renderPagedTable(allSitesData, currentPage, pageSize);
  }
});

/**
 * 渲染媒体类型和账号类型下拉框
 * @param {Object} mediaCodes 媒体类型配置对象
 */
function renderMediaCodes(config) {
  const mediaCodes = config.media_codes;
  const accountTypes = config.account_types;
  // 渲染媒体类型下拉框
  var $mediaType = $('sl-select[name="media_type"]');
  $mediaType.empty();
  if (mediaCodes && typeof mediaCodes === 'object') {
    Object.entries(mediaCodes).forEach(function([code, info]) {
      $mediaType.append(`<sl-option value="${code}">${info.name}</sl-option>`);
    });
  }
  // 渲染账号类型下拉框（与媒体类型一致）
  var $accountType = $('sl-select[name="account_type"]');
  $accountType.empty();
  if (accountTypes && typeof accountTypes === 'object') {
    Object.entries(accountTypes).forEach(function([code, info]) {
      $accountType.append(`<sl-option value="${code}">${info.name}</sl-option>`);
    });
  }
}

/**
 * 页面初始化，后续可扩展事件绑定等
 */
function initPage() {
  // 先获取全局配置
  fetchConfig().then(function(cfg) {
    config = cfg || {};
    // 渲染媒体类型配置
    renderMediaCodes(config);

    // 其它初始化任务
    fetchUsers().then(function(users) {
      allSitesData = users || [];
      currentPage = 1;
      renderPagedTable(allSitesData, currentPage, pageSize);
    });
  });
}

// 页面加载后初始化
$(document).ready(initPage);

// 纯前端筛选功能
function getFilterValues() {
  // 获取筛选表单的所有值
  const form = document.getElementById('filter-form');
  const formData = new FormData(form);
  return {
    account: formData.get('account')?.trim(),
    contact: formData.get('contact')?.trim(),
    description: formData.get('description')?.trim(),
    media_type: formData.getAll('media_type'), // 多选
    account_type: formData.getAll('account_type') // 多选
  };
}

function filterSitesData() {
  const filter = getFilterValues();
  // 过滤allSitesData，返回新数组
  return allSitesData.map(user => {
    // 过滤站点
    const filteredSites = (user.sites || []).filter(site => {
      // 账号/手机号
      if (filter.account && !site.account.includes(filter.account)) return false;
      // 负责人
      if (filter.contact && !site.contact.includes(filter.contact)) return false;
      // 描述
      if (filter.description && !site.description.includes(filter.description)) return false;
      // 媒体类型
      if (filter.media_type.length > 0 && !filter.media_type.includes(String(site.code))) return false;
      // 账号类型（如有）
      if (filter.account_type.length > 0 && !filter.account_type.includes(String(site.account_type))) return false;
      return true;
    });
    return { ...user, sites: filteredSites };
  });
}

// 监听筛选表单提交事件
$(document).on('submit', '#filter-form', function(e) {
  e.preventDefault();
  currentPage = 1;
  const filtered = filterSitesData();
  renderPagedTable(filtered, currentPage, pageSize);
});

// 监听重置按钮
$(document).on('reset', '#filter-form', function(e) {
  setTimeout(() => {
    currentPage = 1;
    renderPagedTable(allSitesData, currentPage, pageSize);
  }, 0);
});

// 添加一行逻辑
$(document).on('click', '#btn-add-row', function () {
  // 如果已存在编辑行，先移除
  $('#sites-table-tbody tr.editing-row').remove();
  // 构造可编辑行
  const $tr = $('<tr class="editing-row"></tr>');
  $tr.append('<td><input type="number" class="edit-user-id" style="width:80px;"></td>');
  $tr.append('<td><sl-select class="edit-media-type" style="width:120px;"></sl-select></td>');
  $tr.append('<td><sl-select class="edit-account-type" style="width:120px;"></sl-select></td>');
  $tr.append('<td><input type="text" class="edit-account" style="width:120px;"></td>');
  $tr.append('<td><input type="text" class="edit-password" style="width:100px;"></td>');
  $tr.append('<td><input type="text" class="edit-contact" style="width:80px;"></td>');
  $tr.append('<td><input type="text" class="edit-description" style="width:120px;"></td>');
  $tr.append('<td>--</td>');
  $tr.append('<td>' +
    '<sl-button size="small" variant="success" class="btn-save-row">保存</sl-button>' +
    '<sl-button size="small" variant="default" class="btn-cancel-row">取消</sl-button>' +
    '</td>');
  $('#sites-table-tbody').prepend($tr);

  // 让 Shoelace 自动注册新插入的 sl-select
  if (window.Shoelace && window.Shoelace.autoloader) {
    window.Shoelace.autoloader();
  }

  // 渲染媒体类型和账号类型下拉框
  const $mediaSelect = $tr.find('.edit-media-type');
  const $accountTypeSelect = $tr.find('.edit-account-type');
  if (config.media_codes) {
    Object.entries(config.media_codes).forEach(([code, info]) => {
      $mediaSelect.append(`<sl-option value="${code}">${info.name}</sl-option>`);
    });
  }
  if (config.account_types) {
    Object.entries(config.account_types).forEach(([code, info]) => {
      $accountTypeSelect.append(`<sl-option value="${code}">${info.name}</sl-option>`);
    });
  }

  // 再次触发autoloader，确保sl-option生效
  if (window.Shoelace && window.Shoelace.autoloader) {
    window.Shoelace.autoloader();
  }
});

// 取消添加
$(document).on('click', '.btn-cancel-row', function () {
  $(this).closest('tr').remove();
});

// 保存添加
$(document).on('click', '.btn-save-row', function () {
  const $tr = $(this).closest('tr');
  // 获取输入值
  const user_id = $tr.find('.edit-user-id').val();
  // 用原生DOM获取sl-select的value
  const code = $tr.find('.edit-media-type')[0]?.value;
  const account_type = $tr.find('.edit-account-type')[0]?.value;
  const account = $tr.find('.edit-account').val();
  const password = $tr.find('.edit-password').val();
  const contact = $tr.find('.edit-contact').val();
  const description = $tr.find('.edit-description').val();
  // 简单校验
  if (!user_id || !code || !account_type || !account) {
    alert('用户ID、媒体类型、账号类型、账号为必填项');
    return;
  }
  // 查找或创建用户
  let user = allSitesData.find(u => String(u.user_id) === String(user_id));
  if (!user) {
    user = { user_id: Number(user_id), sites: [] };
    allSitesData.push(user);
  }
  // 添加新站点
  user.sites.push({
    code: Number(code),
    account_type: Number(account_type),
    account,
    password,
    contact,
    description
  });
  // 移除编辑行并刷新表格
  $tr.remove();
  renderPagedTable(allSitesData, 1, pageSize);
});
