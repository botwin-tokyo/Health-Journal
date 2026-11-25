#!/usr/bin/env bash
set -euo pipefail
repository_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
artifact_dir="$repository_dir/.local/openbao-download"
verification_dir="$repository_dir/.local/openbao-gnupg"
mkdir -p "$artifact_dir" "$verification_dir"
chmod 0700 "$verification_dir"
for asset in openbao_2.7.2_linux_arm64.tar.gz checksums.txt checksums.txt.gpgsig openbao-gpg-pub-20240618.asc; do
  if [[ ! -f "$artifact_dir/$asset" ]]; then
    curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
      "https://github.com/openbao/openbao/releases/download/v2.7.2/$asset" -o "$artifact_dir/$asset"
  fi
done
gpg --homedir "$verification_dir" --import "$artifact_dir/openbao-gpg-pub-20240618.asc"
fingerprint=$(gpg --homedir "$verification_dir" --with-colons --fingerprint D200CD702853E6D0 | awk -F: '$1 == "fpr" { print $10; exit }')
[[ "$fingerprint" == 66D15FDD87287219C8E15478D200CD702853E6D0 ]]
gpg --homedir "$verification_dir" --verify "$artifact_dir/checksums.txt.gpgsig" "$artifact_dir/checksums.txt"
cd "$artifact_dir"
sha256sum --ignore-missing --check checksums.txt
tar --extract --gzip --file openbao_2.7.2_linux_arm64.tar.gz --directory "$artifact_dir" bao
"$artifact_dir/bao" version
