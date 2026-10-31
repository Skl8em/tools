{
  description = "tools — shared toolchain and configuration template for my projects";

  # 26.05 is the last nixpkgs release that supports x86_64-darwin.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-darwin"
        "aarch64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      mkDevShell = import ./nix/dev-shell.nix { inherit nixpkgs; };
    in
    {
      lib = { inherit forAllSystems mkDevShell; };

      # This repository's own shell: the template's tests run copier, and render
      # projects whose devShell comes from mkDevShell above.
      devShells = forAllSystems (system: {
        default = mkDevShell {
          inherit system;
          languages = [
            "python"
            "markdown"
          ];
          packages = [ nixpkgs.legacyPackages.${system}.nixfmt ];
        };
      });

      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt);
    };
}
