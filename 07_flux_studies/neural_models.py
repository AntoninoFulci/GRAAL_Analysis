"""CPU PyTorch ensembles that learn native-strip shapes, never target exposure.

The 387 features are left/right/interpolated flux per event (3 x 128),
followed by left distance, right distance and interpolation weight. The
interpolated shape is a fixed logit offset. Networks learn a residual shape;
only the input interpolation supplies the predicted integral.
"""
from contextlib import contextmanager

import numpy as np

NEURAL_FAMILIES = ('mlp', 'cnn1d')
FIXED_PARAMETERS = dict(epochs=120, initializations=3, learning_rate=.003,
                        device='cpu', threads=1, optimizer='Adam',
                        loss='KL(target_shape || predicted_shape)',
                        preprocessing='training_only_standardization_of_shapes_and_geometry',
                        integral='input_interpolation', residual_logits=True)


@contextmanager
def _deterministic_cpu(torch):
    """Restore process settings and CPU random state after a local fit."""
    threads = torch.get_num_threads()
    deterministic = torch.are_deterministic_algorithms_enabled()
    warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    try:
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        with torch.random.fork_rng(devices=[]):
            yield
    finally:
        torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)
        torch.set_num_threads(threads)


def _features(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 387 or not np.isfinite(values).all():
        raise ValueError('neural features must be finite with shape (n, 387)')
    if np.any(values[:, :384] < 0):
        raise ValueError('donor and interpolation flux must be nonnegative')
    flux = values[:, :384].reshape(-1, 3, 128)
    integrals = flux.sum(axis=2, keepdims=True)
    shapes = np.divide(flux, integrals, out=np.zeros_like(flux), where=integrals > 0)
    transformed = np.c_[shapes.reshape(-1, 384), values[:, 384:]]
    baseline = np.log(np.maximum(shapes[:, 2], 1e-12))
    return transformed, baseline, integrals[:, 2, 0]


def _network(torch, family, width):
    nn = torch.nn
    if family == 'mlp':
        return nn.Sequential(nn.Linear(387, width), nn.Tanh(), nn.Linear(width, width),
                             nn.Tanh(), nn.Linear(width, 128))

    class ConvShape(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.Sequential(nn.Conv1d(6, width, 5, padding=2), nn.Tanh(),
                                        nn.Conv1d(width, width, 5, padding=2), nn.Tanh(),
                                        nn.Conv1d(width, 1, 1))

        def forward(self, x):
            spectra = x[:, :384].reshape(-1, 3, 128)
            geometry = x[:, 384:, None].expand(-1, -1, 128)
            return self.layers(torch.cat((spectra, geometry), dim=1))[:, 0]

    return ConvShape()


class TorchShapeEnsemble:
    """Averaged normalized shapes with an sklearn-compatible predict method."""

    def __init__(self, family, *, width, weight_decay, epochs=120,
                 initializations=3, learning_rate=.003, seed):
        if family not in NEURAL_FAMILIES:
            raise ValueError('unknown neural family')
        if (not isinstance(width, int) or width < 1 or not isinstance(epochs, int) or epochs < 1
                or not isinstance(initializations, int) or initializations < 3
                or not isinstance(seed, (int, np.integer)) or seed < 0
                or not np.isfinite(weight_decay) or weight_decay < 0
                or not np.isfinite(learning_rate) or learning_rate <= 0):
            raise ValueError('invalid neural training parameters')
        self.family, self.width, self.weight_decay = family, width, weight_decay
        self.epochs, self.initializations = epochs, initializations
        self.learning_rate, self.seed = learning_rate, int(seed)

    def fit(self, features, targets):
        import torch

        x, baseline, _ = _features(features)
        targets = np.asarray(targets, dtype=np.float64)
        if (not len(x) or targets.shape != (len(x), 128)
                or not np.isfinite(targets).all() or np.any(targets < 0)):
            raise ValueError('neural targets must be nonnegative finite (n, 128) spectra')
        target_integrals = targets.sum(axis=1, keepdims=True)
        usable = target_integrals[:, 0] > 0
        if not usable.any():
            raise ValueError('neural training needs at least one positive target spectrum')
        x, baseline = x[usable], baseline[usable]
        shape = targets[usable] / target_integrals[usable]
        self.mean_ = x.mean(axis=0)
        self.scale_ = x.std(axis=0)
        self.scale_[self.scale_ < 1e-12] = 1.
        self.models_ = []
        self.diagnostics_ = dict(FIXED_PARAMETERS, family=self.family, width=self.width,
                                 weight_decay=self.weight_decay, epochs=self.epochs,
                                 learning_rate=self.learning_rate, n_training=len(x),
                                 n_zero_targets_omitted=int((~usable).sum()),
                                 torch_version=str(torch.__version__), initializations=[])
        with _deterministic_cpu(torch):
            tx = torch.tensor((x - self.mean_) / self.scale_, dtype=torch.float32)
            tb = torch.tensor(baseline, dtype=torch.float32)
            ty = torch.tensor(shape, dtype=torch.float32)
            for index in range(self.initializations):
                member_seed = self.seed + index * 104729
                # Seed CPU only: training does not initialize an accelerator context.
                torch.random.default_generator.manual_seed(member_seed)
                model = _network(torch, self.family, self.width).cpu()
                optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate,
                                             weight_decay=self.weight_decay)
                losses = []
                model.train()
                for _ in range(self.epochs):
                    optimizer.zero_grad(set_to_none=True)
                    log_shape = torch.log_softmax(tb + model(tx), dim=1)
                    loss = torch.nn.functional.kl_div(log_shape, ty, reduction='batchmean')
                    if not torch.isfinite(loss):
                        raise ValueError('nonfinite neural training loss')
                    losses.append(float(loss.detach()))
                    loss.backward()
                    optimizer.step()
                model.eval()
                with torch.inference_mode():
                    final_loss = float(torch.nn.functional.kl_div(
                        torch.log_softmax(tb + model(tx), dim=1), ty, reduction='batchmean'))
                if not np.isfinite(final_loss):
                    raise ValueError('nonfinite final neural training loss')
                self.models_.append(model)
                self.diagnostics_['initializations'].append(dict(
                    seed=member_seed, initial_loss=losses[0], final_loss=final_loss,
                    loss_history=losses, epochs=self.epochs,
                    parameters=sum(p.numel() for p in model.parameters())))
        return self

    def predict(self, features):
        import torch

        if not hasattr(self, 'models_'):
            raise ValueError('neural estimator must be fitted before prediction')
        x, baseline, integral = _features(features)
        if not len(x):
            return np.empty((0, 128), dtype=float)
        with _deterministic_cpu(torch), torch.inference_mode():
            tx = torch.tensor((x - self.mean_) / self.scale_, dtype=torch.float32)
            tb = torch.tensor(baseline, dtype=torch.float32)
            shapes = [torch.softmax(tb + model(tx), dim=1).numpy().astype(float)
                      for model in self.models_]
        shape = np.mean(shapes, axis=0)
        shape /= shape.sum(axis=1, keepdims=True)
        return shape * integral[:, None]
