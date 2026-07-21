# Changelog

## v0.0.5
### Filter change:
The `DecentVroFilter` now only uses positive detections, leading to more data being ignored (see [this commit](https://github.com/JannisNe/ampel-tdemocracy/commit/c4acba30f5462f096ec4a4ffedac3d7de6543d4f))

### Bug fixes:
* Actually report photometry MJD, not JD [here](https://github.com/JannisNe/ampel-tdemocracy/commit/f64824e6e70a0861d9be83a1dddcb48650ee8961)
* Fix missing square root in circularized error of the mean position [here](https://github.com/JannisNe/ampel-tdemocracy/commit/f7eb317f49010c12b9bacead70a2d466edd69b2a)