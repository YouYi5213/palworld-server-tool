<script setup>
import { ref, onMounted, computed } from "vue";
import { NButton, NSwitch, NInputNumber, NInput, NSelect, NSpace, NTabPane, NTabs, NTag, NIcon, NModal, useMessage } from "naive-ui";
import { UploadOutlined } from "@vicons/material";
import ApiService from "@/service/api";
import { SettingsPowerRound } from "@vicons/material";

const message = useMessage();
const emit = defineEmits(["close"]);

const serverRunning = ref(false);
const configMap = ref({});
const loading = ref(false);
const saving = ref(false);
const activeTab = ref("server");
const showImportModal = ref(false);
const importText = ref("");
const fileInput = ref(null);

function parseIniToMap(text) {
  const map = {};
  const start = text.indexOf("OptionSettings=(");
  if (start === -1) return map;
  let body = text.substring(start + "OptionSettings=(".length);
  let depth = 1;
  let end = 0;
  for (let i = 0; i < body.length; i++) {
    if (body[i] === "(") depth++;
    else if (body[i] === ")") { depth--; if (depth === 0) { end = i; break; } }
  }
  body = body.substring(0, end);
  let i = 0;
  while (i < body.length) {
    const eq = body.indexOf("=", i);
    if (eq === -1) break;
    const key = body.substring(i, eq).trim();
    i = eq + 1;
    if (i >= body.length) break;
    const ch = body[i];
    let val;
    if (ch === '"') {
      const close = body.indexOf('"', i + 1);
      val = body.substring(i + 1, close === -1 ? body.length : close);
      i = close === -1 ? body.length : close + 1;
    } else if (ch === "(") {
      let pd = 1;
      let j = i + 1;
      for (; j < body.length; j++) {
        if (body[j] === "(") pd++;
        else if (body[j] === ")") { pd--; if (pd === 0) break; }
      }
      val = body.substring(i + 1, j);
      i = j + 1;
    } else {
      const comma = body.indexOf(",", i);
      val = body.substring(i, comma === -1 ? body.length : comma).trim();
      i = comma === -1 ? body.length : comma + 1;
    }
    map[key] = val;
  }
  return map;
}

function applyImportMap(map) {
  for (const s of SETTINGS) {
    if (map[s.key] !== undefined) {
      configMap.value[s.key] = map[s.key];
    }
  }
}

const CATEGORIES = [
  { key: "server", label: "服务器设置" },
  { key: "ingame", label: "游戏内设置" },
  { key: "advanced", label: "高级设置" },
];

const SETTINGS = [
  { key: "ServerName", category: "server", label: "服务器名称", type: "string", default: "Default Palworld Server" },
  { key: "ServerDescription", category: "server", label: "服务器描述", type: "string", default: "" },
  { key: "AdminPassword", category: "server", label: "管理员密码", type: "string", default: "" },
  { key: "ServerPassword", category: "server", label: "服务器密码", type: "string", default: "" },
  { key: "PublicPort", category: "server", label: "公共端口", type: "integer", min: 1024, max: 65535, default: 8211 },
  { key: "ServerPlayerMaxNum", category: "server", label: "最大玩家数", type: "integer", min: 1, max: 512, default: 32 },
  { key: "bIsUseBackupSaveData", category: "server", label: "自动备份存档", type: "bool", default: true },
  { key: "AutoSaveSpan", category: "server", label: "自动保存间隔(秒)", type: "float", min: 30, max: 3600, default: 30.0 },
  { key: "LogFormatType", category: "server", label: "日志格式", type: "select", options: ["Text", "Json"], default: "Text" },
  { key: "bEnableVoiceChat", category: "server", label: "启用语音聊天", type: "bool", default: false },
  { key: "RCONEnabled", category: "server", label: "启用 RCON", type: "bool", default: false },
  { key: "RCONPort", category: "server", label: "RCON 端口", type: "integer", min: 1, max: 65535, default: 25575 },
  { key: "RESTAPIEnabled", category: "server", label: "启用 REST API", type: "bool", default: false },
  { key: "RESTAPIPort", category: "server", label: "REST API 端口", type: "integer", min: 1, max: 65535, default: 8212 },
  { key: "bShowPlayerList", category: "server", label: "允许查看玩家列表", type: "bool", default: false },
  { key: "DayTimeSpeedRate", category: "ingame", label: "白天流逝速度", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "NightTimeSpeedRate", category: "ingame", label: "夜间流逝速度", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "ExpRate", category: "ingame", label: "经验值倍率", type: "float", min: 0, max: 20, step: 0.5, default: 1.0 },
  { key: "PalCaptureRate", category: "ingame", label: "捕捉概率倍率", type: "float", min: 0.5, max: 5, step: 0.1, default: 1.0 },
  { key: "PalSpawnNumRate", category: "ingame", label: "帕鲁出现数量倍率", type: "float", min: 0.5, max: 5, step: 0.1, default: 1.0 },
  { key: "PalDamageRateAttack", category: "ingame", label: "帕鲁攻击伤害倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PalDamageRateDefense", category: "ingame", label: "帕鲁承受伤害倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PalStomachDecreaceRate", category: "ingame", label: "帕鲁饱食度降低倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PalStaminaDecreaceRate", category: "ingame", label: "帕鲁耐力降低倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PalAutoHPRegeneRate", category: "ingame", label: "帕鲁生命回复倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PalAutoHpRegeneRateInSleep", category: "ingame", label: "帕鲁睡眠回复倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PlayerDamageRateAttack", category: "ingame", label: "玩家攻击伤害倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PlayerDamageRateDefense", category: "ingame", label: "玩家承受伤害倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PlayerStomachDecreaceRate", category: "ingame", label: "玩家饱食度降低倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PlayerStaminaDecreaceRate", category: "ingame", label: "玩家耐力降低倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PlayerAutoHPRegeneRate", category: "ingame", label: "玩家生命回复倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "PlayerAutoHpRegeneRateInSleep", category: "ingame", label: "玩家睡眠回复倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "WorkSpeedRate", category: "ingame", label: "工作速率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "BuildObjectHpRate", category: "ingame", label: "建筑物生命值倍率", type: "float", min: 0.5, max: 5, step: 0.1, default: 1.0 },
  { key: "BuildObjectDamageRate", category: "ingame", label: "对建筑物伤害倍率", type: "float", min: 0.5, max: 3, step: 0.1, default: 1.0 },
  { key: "BuildObjectDeteriorationDamageRate", category: "ingame", label: "建筑劣化速度倍率", type: "float", min: 0, max: 10, step: 0.1, default: 1.0 },
  { key: "DropItemMaxNum", category: "ingame", label: "掉落物最大数量", type: "integer", min: 0, max: 10000, default: 3000 },
  { key: "ItemWeightRate", category: "ingame", label: "物品重量倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "CollectionDropRate", category: "ingame", label: "道具采集量倍率", type: "float", min: 0.5, max: 5, step: 0.1, default: 1.0 },
  { key: "CollectionObjectHpRate", category: "ingame", label: "可采集物生命值倍率", type: "float", min: 0.5, max: 3, step: 0.1, default: 1.0 },
  { key: "CollectionObjectRespawnSpeedRate", category: "ingame", label: "可采集物重生间隔倍率", type: "float", min: 0.5, max: 5, step: 0.1, default: 1.0 },
  { key: "EnemyDropItemRate", category: "ingame", label: "道具掉落量倍率", type: "float", min: 0.5, max: 5, step: 0.1, default: 1.0 },
  { key: "PalEggDefaultHatchingTime", category: "ingame", label: "巨大蛋孵化时间(小时)", type: "float", min: 0, max: 240, step: 1, default: 72.0 },
  { key: "bEnableInvaderEnemy", category: "ingame", label: "启用袭击事件", type: "bool", default: true },
  { key: "DeathPenalty", category: "ingame", label: "死亡惩罚", type: "select", options: ["None", "Item", "ItemAndEquipment", "All"], default: "All" },
  { key: "GuildPlayerMaxNum", category: "ingame", label: "公会最大玩家数", type: "integer", min: 1, max: 100, default: 20 },
  { key: "BaseCampMaxNumInGuild", category: "ingame", label: "公会据点最大数量", type: "integer", min: 1, max: 50, default: 3 },
  { key: "BaseCampWorkerMaxNum", category: "ingame", label: "据点帕鲁上限", type: "integer", min: 1, max: 50, default: 15 },
  { key: "SupplyDropSpan", category: "ingame", label: "空投间隔(分钟)", type: "integer", min: 0, max: 1000, default: 180 },
  { key: "EquipmentDurabilityDamageRate", category: "ingame", label: "装备耐久消耗倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "MonsterFarmActionSpeedRate", category: "ingame", label: "牧场产出速度倍率", type: "float", min: 0.1, max: 5, step: 0.1, default: 1.0 },
  { key: "bEnablePlayerToPlayerDamage", category: "advanced", label: "启用PVP伤害", type: "bool", default: false },
  { key: "bEnableFriendlyFire", category: "advanced", label: "启用友伤", type: "bool", default: false },
  { key: "bIsPvP", category: "advanced", label: "PVP模式", type: "bool", default: false },
  { key: "bHardcore", category: "advanced", label: "硬核模式", type: "bool", default: false },
  { key: "bActiveUNKO", category: "advanced", label: "激活帕鲁便便", type: "bool", default: false },
  { key: "bAutoResetGuildNoOnlinePlayers", category: "advanced", label: "自动重置空公会", type: "bool", default: false },
  { key: "bEnableNonLoginPenalty", category: "advanced", label: "未登录惩罚", type: "bool", default: true },
  { key: "bEnableFastTravel", category: "advanced", label: "启用快速传送", type: "bool", default: true },
  { key: "bIsStartLocationSelectByMap", category: "advanced", label: "地图选择复活点", type: "bool", default: true },
  { key: "bExistPlayerAfterLogout", category: "advanced", label: "登出后人物存在", type: "bool", default: false },
  { key: "bCanPickupOtherGuildDeathPenaltyDrop", category: "advanced", label: "可拾取他人死亡掉落", type: "bool", default: false },
  { key: "bBuildAreaLimit", category: "advanced", label: "建筑区域限制", type: "bool", default: false },
  { key: "bAllowClientMod", category: "advanced", label: "允许客户端Mod", type: "bool", default: true },
  { key: "bIsShowJoinLeftMessage", category: "advanced", label: "显示进出消息", type: "bool", default: true },
  { key: "bAllowGlobalPalboxExport", category: "advanced", label: "允许导出帕鲁基因", type: "bool", default: true },
  { key: "bAllowGlobalPalboxImport", category: "advanced", label: "允许导入帕鲁基因", type: "bool", default: false },
  { key: "bEnableDefenseOtherGuildPlayer", category: "advanced", label: "据点防御其他公会", type: "bool", default: false },
  { key: "bInvisibleOtherGuildBaseCampAreaFX", category: "advanced", label: "隐藏其他公会据点特效", type: "bool", default: false },
  { key: "bEnableBuildingPlayerUIdDisplay", category: "advanced", label: "显示建筑建造者", type: "bool", default: false },
  { key: "bAllowEnhanceStat_Health", category: "advanced", label: "允许加点-生命", type: "bool", default: true },
  { key: "bAllowEnhanceStat_Attack", category: "advanced", label: "允许加点-攻击", type: "bool", default: true },
  { key: "bAllowEnhanceStat_Stamina", category: "advanced", label: "允许加点-体力", type: "bool", default: true },
  { key: "bAllowEnhanceStat_Weight", category: "advanced", label: "允许加点-负重", type: "bool", default: true },
  { key: "bAllowEnhanceStat_WorkSpeed", category: "advanced", label: "允许加点-工作速度", type: "bool", default: true },
  { key: "bEnableFastTravelOnlyBaseCamp", category: "advanced", label: "仅基地可快速旅行", type: "bool", default: false },
  { key: "GuildRejoinCooldownMinutes", category: "advanced", label: "公会重加冷却(分钟)", type: "integer", min: 0, max: 1440, default: 0 },
  { key: "BlockRespawnTime", category: "advanced", label: "阻止重生时间(秒)", type: "float", min: 0, max: 60, step: 0.5, default: 5.0 },
  { key: "AutoResetGuildTimeNoOnlinePlayers", category: "advanced", label: "空公会重置时间(小时)", type: "float", min: 0, max: 240, step: 1, default: 72.0 },
  { key: "DropItemAliveMaxHours", category: "advanced", label: "掉落物存活(小时)", type: "float", min: 0, max: 240, step: 1, default: 1.0 },
  { key: "ServerReplicatePawnCullDistance", category: "advanced", label: "同步距离", type: "integer", min: 5000, max: 15000, default: 15000 },
  { key: "ChatPostLimitPerMinute", category: "advanced", label: "每分钟聊天限制", type: "integer", min: 0, max: 100, default: 10 },
];

const visibleSettings = computed(() => SETTINGS.filter(s => s.category === activeTab.value));

const getVal = (setting) => {
  const v = configMap.value[setting.key];
  if (v === undefined || v === null) return setting.default;
  return v;
};

const fetchConfig = async () => {
  loading.value = true;
  try {
    const { data } = await new ApiService().fetch(`/api/server/config`).get().json();
    if (data.value) {
      serverRunning.value = data.value.running;
      if (data.value.entries) {
        for (const entry of data.value.entries) {
          configMap.value[entry.key] = entry.value;
        }
      }
    }
  } catch (e) {
    message.error("读取配置失败");
  }
  loading.value = false;
};

const handleSave = async () => {
  saving.value = true;
  const entries = SETTINGS.map(s => ({
    key: s.key,
    value: String(getVal(s)),
  }));
  try {
    const { data, statusCode } = await new ApiService().fetch(`/api/server/config`).put({ entries }).json();
    if (statusCode.value === 200) {
      message.success("保存成功! 重启服务端后生效");
    } else {
      message.error("保存失败: " + (data.value?.error || "未知错误"));
    }
  } catch (e) {
    message.error("保存失败: " + e.message);
  }
  saving.value = false;
};

const updateVal = (setting, val) => {
  configMap.value[setting.key] = setting.type === "bool" ? (val ? "True" : "False") : String(val);
};

const handleFileImport = (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    const text = ev.target?.result;
    if (typeof text === "string") {
      const map = parseIniToMap(text);
      applyImportMap(map);
      message.success("已从文件导入 " + Object.keys(map).length + " 项配置");
    }
  };
  reader.readAsText(file);
  e.target.value = "";
};

const handlePasteImport = () => {
  const text = importText.value;
  if (!text.trim()) {
    message.warning("请先粘贴配置文件内容");
    return;
  }
  const map = parseIniToMap(text);
  if (Object.keys(map).length === 0) {
    message.error("未识别到有效的配置内容，请检查格式");
    return;
  }
  applyImportMap(map);
  showImportModal.value = false;
  importText.value = "";
  message.success("已导入 " + Object.keys(map).length + " 项配置");
};

onMounted(() => {
  fetchConfig();
});
</script>

<template>
  <div class="server-config">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold">服务器配置</span>
        <n-tag v-if="serverRunning" type="error" round size="small">
          <template #icon><n-icon><SettingsPowerRound /></n-icon></template>
          服务端运行中，只读
        </n-tag>
        <n-tag v-else type="success" round size="small">
          服务端已停止，可编辑
        </n-tag>
      </div>
      <n-space>
        <input ref="fileInput" type="file" accept=".ini,.txt" style="display:none" @change="handleFileImport" />
        <n-button size="small" secondary :disabled="serverRunning" @click="fileInput?.click()">
          <template #icon><n-icon><UploadOutlined /></n-icon></template>
          上传文件
        </n-button>
        <n-button size="small" secondary :disabled="serverRunning" @click="showImportModal = true">
          粘贴导入
        </n-button>
      </n-space>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane v-for="cat in CATEGORIES" :key="cat.key" :name="cat.key" :tab="cat.label">
        <div v-if="loading" class="text-center py-8 text-gray-400">加载中...</div>
        <div v-else class="space-y-1 max-h-96 overflow-y-auto">
          <div v-for="s in visibleSettings" :key="s.key"
            class="flex items-center justify-between py-2 px-3 rounded hover:bg-gray-50 dark:hover:bg-gray-800 min-h-12"
          >
            <div class="flex-1 min-w-0 mr-4">
              <div class="text-sm font-medium">{{ s.label }}</div>
              <div class="text-xs text-gray-400 truncate">{{ s.key }}</div>
            </div>
            <div class="flex-shrink-0">
              <n-switch v-if="s.type === 'bool'" :value="getVal(s) === 'True'" :disabled="serverRunning" @update:value="v => updateVal(s, v)" />
              <n-select v-else-if="s.type === 'select'" :value="getVal(s)" :disabled="serverRunning" :options="s.options.map(o => ({label: o, value: o}))" style="width:200px" @update:value="v => updateVal(s, v)" />
              <n-input-number v-else-if="s.type === 'float' || s.type === 'integer'" :value="Number(getVal(s)) || 0" :disabled="serverRunning" :min="s.min" :max="s.max" :step="s.step || (s.type === 'integer' ? 1 : 0.1)" style="width:160px" @update:value="v => updateVal(s, v)" />
              <n-input v-else :value="getVal(s)" :disabled="serverRunning" style="width:260px" @update:value="v => updateVal(s, v)" />
            </div>
          </div>
        </div>
      </n-tab-pane>
    </n-tabs>

    <div class="flex justify-end gap-3 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
      <n-button @click="$emit('close')">关闭</n-button>
      <n-button type="primary" :disabled="serverRunning || loading" :loading="saving" @click="handleSave">
        保存配置
      </n-button>
    </div>
  </div>

  <n-modal v-model:show="showImportModal" preset="card" style="width: 90%; max-width: 700px" title="粘贴配置文件" size="large" :bordered="false" :segmented="{ content: true }">
    <div>
      <p class="text-sm text-gray-400 mb-3">请复制 PalWorldSettings.ini 的内容粘贴到下方文本框，点击确认后自动识别并填充配置项。</p>
      <n-input type="textarea" v-model:value="importText" rows="12" placeholder="在此粘贴 PalWorldSettings.ini 内容..." />
    </div>
    <template #footer>
      <div class="flex justify-end gap-3">
        <n-button @click="showImportModal = false">取消</n-button>
        <n-button type="primary" @click="handlePasteImport">确认导入</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.server-config {
  min-height: 400px;
}
</style>
