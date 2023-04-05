# IAM Bundle
This repository hosts IAM bundle definitions and tests.

## Generate a bundle
In order to generate a bundle file, clone this repository and use the `render-{channel}` utility.
For example, to get the bundle from `edge` channel, run `tox -e render-edge`.

If you would like to deploy the bundle with a locally built charm, modify the file adding its path and image:
```yaml
  hydra:
    charm: ./path-to-your.charm
    resources:
      oci-image: oryd/hydra:v2.0.3
    scale: 1
    series: jammy
    trust: true
```

## Deploy a bundle
To deploy the bundle, run `juju deploy ./bundle-edge.yaml --trust`.

## Test the bundle
Integration tests can be run with `tox`.

In order to launch tests against an already deployed bundle, run `tox -e integration -- --model=your-model --keep-models --no-deploy`.
