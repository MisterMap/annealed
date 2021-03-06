import torch.nn as nn
from .vae_hvi import VAEHVI
import torch
import torch.nn
import numpy as np


# noinspection PyTypeChecker
class VAEHVIAVO(VAEHVI):
    def __init__(self, input_dimension=28, latent_dimension=40, hidden_dimensions=(300, 300), depth=5,
                 transition_hidden_dimension=40, alpha=0.2, **kwargs):
        super().__init__(input_dimension, latent_dimension, hidden_dimensions, depth,
                         transition_hidden_dimension, **kwargs)
        self._alphas = np.linspace(1. / depth, 1, depth)
        self._alpha = alpha

    def forward(self, x):
        random_alpha = np.random.ranf()
        if random_alpha > self._alpha:
            return super().forward(x)
        hidden_x = self.encoder(x)
        z_mu = self._mu_linear(hidden_x)
        z_logvar = self._logvar_linear(hidden_x)
        epsilon = torch.randn_like(z_mu)
        z = z_mu + torch.exp(0.5 * z_logvar) * epsilon

        previous_log_probability = torch.sum(
            torch.distributions.normal.Normal(z_mu, torch.exp(0.5 * z_logvar)).log_prob(z), dim=1)
        loss = 0
        beta = self.calculate_beta()
        reconstructed_x = None
        for alpha, transition in zip(self._alphas, self._transitions):
            previous_log_probability = previous_log_probability.detach()
            z = z.detach()
            z, log_probability = transition(z, hidden_x)
            reconstructed_x = self.decoder(z)
            prior_z = torch.sum(torch.distributions.normal.Normal(0, 1).log_prob(z), dim=1)
            f_t = self.nll_part_loss(reconstructed_x, x) - prior_z * beta
            f_0 = -torch.sum(torch.distributions.normal.Normal(z_mu, torch.exp(0.5 * z_logvar)).log_prob(z),
                            dim=1)
            annealed_loss = alpha * f_t + (1 - alpha) * f_0
            loss += annealed_loss + (log_probability + previous_log_probability) * beta
            previous_log_probability += log_probability

        kl_part = previous_log_probability - torch.sum(torch.distributions.normal.Normal(0, 1).log_prob(z), dim=1)
        scale = x.size()[0]
        kl_part = torch.sum(kl_part) / scale
        x: torch.Tensor
        nll_part = self.nll_part_loss(reconstructed_x, x) / scale
        loss = torch.mean(loss)
        return reconstructed_x, loss, nll_part, kl_part
