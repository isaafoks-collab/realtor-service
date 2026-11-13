#!/usr/bin/env bash
# Публикация витрины после успешного утреннего прогона:
# генерация index.html из listings.db → коммит в ветку gh-pages.
# Вызывается из morning.sh с "|| true" — падение НЕ должно ронять прогон.
set -u
cd /opt/realtor-service
PY=/opt/realtor-service/venv/bin/python3
set -a; . /etc/realtor/env; set +a
REMOTE="https://x-access-token:${GITHUB_REPO_TOKEN}@github.com/isaafoks-collab/realtor-service.git"

# 1) Генерация (сеть не нужна)
$PY vitrina_gen.py --db listings.db --out /tmp/vitrina-index.html || { echo "vitrina: генерация не удалась — пропускаю"; exit 0; }

# 2) Свежий gh-pages в отдельный worktree (рабочую копию main не трогаем)
git fetch "$REMOTE" gh-pages || { echo "vitrina: fetch не удался — пропускаю"; exit 0; }
git worktree remove --force /tmp/vitrina-pages 2>/dev/null || rm -rf /tmp/vitrina-pages
git worktree add -f /tmp/vitrina-pages FETCH_HEAD || { echo "vitrina: worktree не удался — пропускаю"; exit 0; }

cp /tmp/vitrina-index.html /tmp/vitrina-pages/index.html

# 3) Коммит и пуш только при реальных изменениях
cd /tmp/vitrina-pages
if git diff --quiet; then
  echo "vitrina: без изменений"
else
  git add index.html
  git -c user.name=realtor-vitrina -c user.email=vitrina@realtor.service \
      commit -m "витрина: авто-обновление после утреннего прогона" || true
  if git push "$REMOTE" HEAD:gh-pages; then
    echo "vitrina: опубликовано"
  else
    echo "vitrina: push не удался"
  fi
fi
cd /opt/realtor-service
git worktree remove --force /tmp/vitrina-pages 2>/dev/null || true
rm -f /tmp/vitrina-index.html
