// 全局配置对象
var config = {};

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
 * 渲染表格内容
 * @param {Array} data 站点数据数组
 */
function renderTable(data) {
  const $tbody = $('#sites-table-tbody');
  $tbody.empty(); // 每次渲染前先清空内容，防止脏数据
  if (!Array.isArray(data) || data.length === 0) {
    $tbody.append('<tr><td colspan="7" style="text-align:center;">暂无数据</td></tr>');
    return;
  }
  let hasData = false;
  data.forEach(function(user) {
    if (!user.sites || !Array.isArray(user.sites) || user.sites.length === 0) return;
    user.sites.forEach(function(site) {
      hasData = true;
      const $tr = $('<tr></tr>');
      // 用户ID
      $tr.append(`<td>${user.user_id !== undefined ? user.user_id : ''}</td>`);
      // 媒体类型（翻译name）
      const mediaType = config.media_codes && config.media_codes[site.code];
      $tr.append(`<td>${mediaType !== undefined ? mediaType.name : ''}</td>`);
      // 账号/手机号
      $tr.append(`<td>${site.account !== undefined ? site.account : ''}</td>`);
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
  });
  if (!hasData) {
    $tbody.append('<tr><td colspan="7" style="text-align:center;">暂无数据</td></tr>');
  }
}

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
      renderTable(users);
      // TODO: 这里可以绑定表格点击等事件
    });
  });
}

// 页面加载后初始化
$(document).ready(initPage);
